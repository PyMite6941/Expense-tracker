import json
import os

import pandas as pd
from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import tool
from pydantic import BaseModel


# ── Shared LLMs ───────────────────────────────────────────────────────────────

def _smart_llm():
    return LLM(
        model="openrouter/deepseek/deepseek-r1:free",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        max_tokens=4096,
        temperature=0.1,
        max_retries=2,
        timeout=60,
    )

def _fast_llm():
    return LLM(
        model="openrouter/meta-llama/llama-3.1-8b-instruct:free",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        max_tokens=2048,
        temperature=0.3,
        max_retries=2,
        timeout=30,
    )


# ── Pydantic output schema ────────────────────────────────────────────────────

class Report(BaseModel):
    summary: str
    key_findings: list[str]
    anomalies: list[str]
    recommendations: list[str]


# ── Module-level tools (CrewAI @tool must be on plain functions) ──────────────

def _parse_input(data) -> list:
    """Accept a list or a JSON string and always return a list."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return []
    return data if isinstance(data, list) else []


@tool("process_data")
def process_data(data: str) -> str:
    """Clean and summarize expense data. Input: JSON array of expense objects."""
    rows = _parse_input(data)
    if not rows:
        return "No data to process."
    df = pd.DataFrame(rows).dropna()
    return df.to_string(index=False)


@tool("analyze_data")
def analyze_data(data: str) -> str:
    """Compute summary statistics on expense data. Input: JSON array of expense objects."""
    rows = _parse_input(data)
    if not rows:
        return "No data to analyze."
    df = pd.DataFrame(rows)
    numeric = df.select_dtypes(include="number")
    if numeric.empty:
        return "No numeric columns found."
    return numeric.describe().to_string()


@tool("classify_expenses")
def classify_expenses(data: str) -> str:
    """Assign a subcategory to each expense based on tags, notes, and merchant name. Input: JSON array."""
    subcategory_map = {
        "food": ["Dining Out", "Groceries", "Coffee & Drinks", "Fast Food", "Meal Prep"],
        "transport": ["Fuel", "Public Transit", "Rideshare", "Parking", "Car Maintenance"],
        "entertainment": ["Streaming", "Games", "Events & Concerts", "Books", "Hobbies"],
        "health": ["Pharmacy", "Gym", "Doctor Visits", "Mental Health", "Supplements"],
        "shopping": ["Clothing", "Electronics", "Home & Garden", "Personal Care", "Gifts"],
        "bills": ["Rent/Mortgage", "Utilities", "Internet", "Phone", "Insurance"],
    }
    rows = _parse_input(data)
    if not rows:
        return "No expenses to classify."
    results = []
    for item in rows:
        text = " ".join([
            str(item.get("tags", "")),
            str(item.get("notes", "")),
            str(item.get("purchased", "")),
        ]).lower()
        assigned = "Other"
        for category, subcats in subcategory_map.items():
            if category in text:
                assigned = subcats[0]
                break
        results.append({
            "id": item.get("id"),
            "purchased": item.get("purchased"),
            "price": item.get("price"),
            "subcategory": assigned,
            "original_tags": item.get("tags"),
        })
    return pd.DataFrame(results).to_string(index=False)


@tool("detect_anomalies_tool")
def detect_anomalies_tool(data: str) -> str:
    """Flag expenses whose price is more than 2 std-devs above the mean. Input: JSON array."""
    rows = _parse_input(data)
    if not rows:
        return "No data provided."
    df = pd.DataFrame(rows)
    if "price" not in df.columns:
        return "No price column found."
    mean = df["price"].mean()
    std = df["price"].std()
    if pd.isna(std) or std == 0:
        return "Insufficient variance to detect anomalies."
    threshold = mean + 2 * std
    flagged = df[df["price"] > threshold]
    if flagged.empty:
        return "No anomalies detected — all expenses are within normal range."
    cols = [c for c in ["id", "purchased", "price", "date", "tags"] if c in flagged.columns]
    return flagged[cols].to_string(index=False)


@tool("summarize_patterns")
def summarize_patterns(data: str) -> str:
    """Identify top spending categories and monthly totals. Input: JSON array."""
    rows = _parse_input(data)
    if not rows:
        return "No data provided."
    df = pd.DataFrame(rows)
    lines = []
    if "tags" in df.columns and "price" in df.columns:
        top = df.groupby("tags")["price"].sum().sort_values(ascending=False).head(5)
        lines.append("Top spending categories:\n" + top.to_string())
    if "date" in df.columns and "price" in df.columns:
        df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M")
        monthly = df.groupby("month")["price"].sum()
        lines.append("\nMonthly totals:\n" + monthly.to_string())
    return "\n".join(lines) if lines else "Insufficient data for pattern analysis."


# ── Basic analysis crew (free tier) ──────────────────────────────────────────

class Bots:
    def __init__(self, context: str):
        self.context = context

    def create_agents(self):
        self.context_agent = Agent(
            role="Analysis Directive Specialist",
            goal=(
                "Read the user's raw context and rewrite it as a precise, unambiguous "
                "analysis directive specifying: the core question, the relevant columns, "
                "the analysis type, and any constraints."
            ),
            backstory=(
                "You translate vague requests into sharp, actionable instructions for data analysts. "
                "You never perform analysis yourself — your only job is clarity."
            ),
            tools=[],
            verbose=True,
            memory=False,
            llm=_fast_llm(),
            allow_delegation=False,
            cache=True,
        )
        self.data_analyst = Agent(
            role="Senior Data Analyst",
            goal=(
                "Analyze the provided dataset and extract accurate, relevant insights "
                "that directly answer the directive. Never speculate beyond what the data shows."
            ),
            backstory=(
                "You are a rigorous data analyst. You clean data before drawing conclusions, "
                "back every finding with statistics, and stay strictly within the scope of your directive."
            ),
            tools=[process_data, analyze_data],
            verbose=True,
            memory=True,
            llm=_smart_llm(),
            max_rpm=15,
            allow_delegation=False,
            cache=True,
        )

    def create_tasks(self):
        self.interpret_task = Task(
            description=(
                f"The user wants this analyzed:\n\nCONTEXT: {self.context}\n\n"
                "Rewrite as a 3-5 sentence directive addressed directly to a data analyst. "
                "Specify: the core question, relevant columns, analysis type, and any constraints."
            ),
            expected_output=(
                "3-5 plain sentences. No headers or bullets. A direct instruction to a data analyst."
            ),
            agent=self.context_agent,
        )
        self.analyze_task = Task(
            description=(
                f"DIRECTIVE: {self.context}\n\n"
                "1. Use process_data to clean the dataset.\n"
                "2. Use analyze_data for summary statistics.\n"
                "3. Answer the directive with specific findings."
            ),
            expected_output=(
                "Data quality summary, key statistics, 3-5 findings, 2-3 recommendations."
            ),
            tools=[process_data, analyze_data],
            agent=self.data_analyst,
            context=[self.interpret_task],
            output_file="/tmp/output.log",
            human_input=False,
        )

    def create_crew(self, data):
        self.create_agents()
        self.create_tasks()
        crew = Crew(
            agents=[self.data_analyst],
            tasks=[self.analyze_task],
            process=Process.sequential,
            verbose=True,
            memory=True,
            embedder={"provider": "fastembed", "config": {"model": "BAAI/bge-small-en-v1.5"}},
        )
        crew.kickoff(inputs={"data": json.dumps(data)})


# ── Advanced categorization crew (Pro/Max tier, JWT-gated) ────────────────────

class AdvancedCategorizationCrew:
    def __init__(self, context: str):
        self.context = context

    def create_agents(self):
        llm = _smart_llm()
        self.categorizer = Agent(
            role="Expense Categorization Specialist",
            goal=(
                "Assign a precise subcategory to every expense using classify_expenses. "
                "No expense should remain as 'Other' if the merchant name or notes give any signal."
            ),
            backstory=(
                "You are a meticulous financial analyst. You use every signal — merchant names, "
                "notes, tags, amounts — to assign the most specific subcategory possible."
            ),
            tools=[classify_expenses],
            verbose=True,
            memory=False,
            llm=llm,
            allow_delegation=False,
            cache=True,
        )
        self.pattern_detector = Agent(
            role="Spending Pattern Analyst",
            goal=(
                "Use summarize_patterns and detect_anomalies_tool to surface trends and flag outliers. "
                "Every finding must reference a specific number from the data."
            ),
            backstory=(
                "You read spending data like a doctor reads vitals — spotting drift, stress, and opportunity. "
                "You never speculate; every claim is grounded in data."
            ),
            tools=[summarize_patterns, detect_anomalies_tool],
            verbose=True,
            memory=True,
            llm=llm,
            max_rpm=10,
            allow_delegation=False,
            cache=True,
        )
        self.advisor = Agent(
            role="Personal Finance Advisor",
            goal=(
                "Write 3-5 specific, quantified budget recommendations based only on the analysis. "
                "Every recommendation must name a dollar amount or percentage target."
            ),
            backstory=(
                "You are a certified financial planner. You never say 'spend less on X' — "
                "you say 'reduce dining out from $340 to $200/month.' Every recommendation is measurable."
            ),
            tools=[],
            verbose=True,
            memory=True,
            llm=llm,
            allow_delegation=False,
            cache=True,
        )

    def create_tasks(self):
        self.categorize_task = Task(
            description=(
                f"User context: {self.context}\n\n"
                "Call classify_expenses with the full expense list as a JSON string. "
                "Return the complete enriched table."
            ),
            expected_output=(
                "A table with columns: id, purchased, price, subcategory, original_tags. "
                "Every row has a non-empty subcategory."
            ),
            agent=self.categorizer,
        )
        self.pattern_task = Task(
            description=(
                "Call summarize_patterns to get top categories and monthly totals.\n"
                "Call detect_anomalies_tool to flag outlier transactions.\n"
                "Report findings with specific numbers — no vague statements."
            ),
            expected_output=(
                "3-6 findings referencing specific numbers. At least one about monthly trends "
                "and one about anomalies (or explicitly stating none were found)."
            ),
            agent=self.pattern_detector,
            context=[self.categorize_task],
        )
        self.advice_task = Task(
            description=(
                "Synthesize the categorization and pattern findings into a final report. "
                'Output must be a JSON object: {"summary": str, "key_findings": [str], '
                '"anomalies": [str], "recommendations": [str]}'
            ),
            expected_output=(
                'A JSON object with keys: summary, key_findings, anomalies, recommendations.'
            ),
            agent=self.advisor,
            context=[self.categorize_task, self.pattern_task],
            output_pydantic=Report,
        )

    def run(self, expenses: list) -> dict:
        self.create_agents()
        self.create_tasks()
        crew = Crew(
            agents=[self.categorizer, self.pattern_detector, self.advisor],
            tasks=[self.categorize_task, self.pattern_task, self.advice_task],
            process=Process.sequential,
            verbose=True,
            memory=True,
            embedder={"provider": "fastembed", "config": {"model": "BAAI/bge-small-en-v1.5"}},
        )
        result = crew.kickoff(inputs={"data": json.dumps(expenses)})
        if hasattr(result, "pydantic") and result.pydantic:
            return result.pydantic.model_dump()
        return {"summary": str(result), "key_findings": [], "anomalies": [], "recommendations": []}
