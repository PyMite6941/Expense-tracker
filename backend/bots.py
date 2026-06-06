from crewai import Agent, Crew, Task, Process, LLM
from crewai.tools import tool
import os
import pandas as pd
from pydantic import BaseModel


class Report(BaseModel):
    summary: str
    key_findings: list[str]
    anomalies: list[str]
    recommendations: list[str]

class Bots:
    def __init__(self,context:str):
        self.context = context
        self.smart_llm = LLM(
            model="openrouter/deepseek/deepseek-r1:free",
            api_key=os.getenv('OPENROUTER_API_KEY'),
            tokens=4096,
            temperature=0.1,
            max_retries=2,
            timeout=30
        )

        self.fast_llm = LLM(
            model="openrouter/groq/groq-1:free",
            api_key=os.getenv('OPENROUTER_API_KEY'),
            tokens=4096,
            temperature=0.3,
            max_retries=2,
            timeout=30
        )

    @tool("process_data")
    def process_data(data:list) -> str:
        """Process data by cleaning and summarizing it."""
        dataset = pd.read_json(data)
        dataset = dataset.dropna()
        return dataset.to_string(index=False)

    @tool("analyze_data")
    def analyze_data(data:list) -> str:
        """Analyze the dataset and return a summary of its key characteristics."""
        dataset = pd.read_json(data) 
        summary = dataset.describe()
        return summary.to_string()
    
    @tool("group_data")
    def group_data(data:list) -> str:
        """Group data by the category parameter"""
        if not 'category' in data[0] or not 'tags' in data[0]:
            return {'success':False,'message':'The scope of this data is either too large or too small.'}
        grouped = []
        for element in data:
            category = data.get('category','general')
            if not category in grouped:
                new_category = []
                grouped.append(new_category)
            count = 0
            for group in grouped:
                if group == category:
                    break
                count += 1
            grouped[count].append(element)
        return {'success':True,'message':'Successfully sorted the data','data':grouped}

    def create_agents(self):
        self.context_agent = Agent(
            role="Analysis Directive Specialist",
            goal=(
                "Read the user's raw context and rewrite it as a precise, unambiguous "
                "analysis directive. Identify the core question, the most relevant columns "
                "or metrics, and the exact type of analysis needed (trend, comparison, "
                "anomaly, summary, correlation). Output only the directive — nothing else."
            ),
            backstory=(
                "You are an expert at translating vague or freeform requests into sharp, "
                "actionable instructions for data analysts. You have a talent for identifying "
                "what someone actually wants to know versus what they literally said. "
                "You never perform analysis yourself — your only job is to make the analyst's "
                "directive so clear that there is no room for misinterpretation."
            ),
            tools=[],
            verbose=True,
            memory=False,
            llm=self.fast_llm,
            allow_delegation=False,
            cache=True,
        )
        self.data_analyst = Agent(
            role="Senior Data Analyst",
            goal=(
                "Analyze the provided dataset and extract accurate, relevant insights "
                "that directly answer the user's context. Prioritize patterns, trends, and "
                "anomalies most pertinent to the question asked. Never speculate beyond what the data shows."
            ),
            backstory=(
                "You are a rigorous data analyst with experience across many domains and dataset types. "
                "You always clean data before drawing conclusions, back every finding with statistics, "
                "and present results in plain language scoped precisely to the question you were given. "
                "You do not invent numbers or go beyond the scope of your directive."
            ),
            tools=[self.process_data, self.analyze_data],
            verbose=True,
            memory=True,
            llm=self.smart_llm,
            max_rpm=15,
            allow_delegation=False,
            cache=True
        )
        self.grouper = Agent(role="Professional Data Classifier",tools=[self.group_data],verbose=True,memory=True,llm=self.smart_llm,max_rpm=15,allow_delegation=False,cache=True)

    def create_tasks(self):
        self.interpret_task = Task(
            description=(
                f"The user has provided this context about what they want analyzed:\n\n"
                f"CONTEXT: {self.context}\n\n"
                "Rewrite this into a structured analysis directive by answering these four questions:\n"
                "1. What is the single core question to answer?\n"
                "2. Which columns or metrics are most relevant to that question?\n"
                "3. What analysis type is needed — trend over time, comparison between groups, "
                "anomaly detection, statistical summary, or correlation?\n"
                "4. Are there any constraints or focus areas implied by the context "
                "(e.g. a date range, a specific user, a threshold)?\n\n"
                "Write the final directive as 3-5 plain sentences addressed directly to a data analyst."
            ),
            expected_output=(
                "A single block of 3-5 plain sentences. No headers, no bullet points, no preamble. "
                "Written as a direct instruction to a data analyst. Must specify: the question to answer, "
                "the relevant columns, the analysis type, and any constraints."
            ),
            agent=self.context_agent,
        )
        self.analyze_task = Task(
            description=(
                f"You have been given a dataset and the following analysis directive:\n\n"
                f"DIRECTIVE: {self.context}\n\n"
                "Step 1: Use the process_data tool to clean the dataset and get a readable view.\n"
                "Step 2: Use the analyze_data tool to compute summary statistics.\n"
                "Step 3: Using only what the data shows, answer the directive precisely — "
                "identify relevant trends, patterns, and anomalies."
            ),
            expected_output=(
                "A structured data analysis report containing:\n"
                "1. Data quality summary (rows cleaned, missing values removed)\n"
                "2. Key statistics relevant to the directive (averages, ranges, outliers)\n"
                "3. 3-5 findings that directly answer the directive\n"
                "4. 2-3 actionable recommendations based solely on the data"
            ),
            tools=[self.process_data, self.analyze_data],
            agent=self.data_analyst,
            context=[self.interpret_task],
            output_file="output.log",
            human_input=False
        )

    def create_crew(self,data):
        self.crew = Crew(
            agents=[self.data_analyst],
            tasks=[self.analyze_task],
            process=Process.sequential,
            verbose=True,
            memory=True,
            embedder = {
                "provider": "fastembed",
                "config": {
                    "model": "BAAI/bge-small-en-v1.5",
                }
            }
        )
        self.crew.kickoff(inputs={"data": data})


class AdvancedCategorizationCrew:
    """Pro-tier CrewAI crew — requires a valid JWT with advanced_categorization feature."""

    SUBCATEGORY_MAP = {
        "food": ["Dining Out", "Groceries", "Coffee & Drinks", "Fast Food", "Meal Prep"],
        "transport": ["Fuel", "Public Transit", "Rideshare", "Parking", "Car Maintenance"],
        "entertainment": ["Streaming", "Games", "Events & Concerts", "Books", "Hobbies"],
        "health": ["Pharmacy", "Gym", "Doctor Visits", "Mental Health", "Supplements"],
        "shopping": ["Clothing", "Electronics", "Home & Garden", "Personal Care", "Gifts"],
        "bills": ["Rent/Mortgage", "Utilities", "Internet", "Phone", "Insurance"],
    }

    def __init__(self, context: str):
        self.context = context
        self.llm = LLM(
            model="openrouter/deepseek/deepseek-r1:free",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            tokens=4096,
            temperature=0.1,
            max_retries=2,
            timeout=45,
        )

    @tool("classify_expenses")
    def classify_expenses(data: list) -> str:
        """Assign a subcategory to each expense based on its tags, notes, and purchase name."""
        results = []
        for item in data:
            tags = str(item.get("tags", "")).lower()
            notes = str(item.get("notes", "")).lower()
            purchased = str(item.get("purchased", "")).lower()
            text = f"{tags} {notes} {purchased}"

            assigned = "Other"
            for category, subcats in AdvancedCategorizationCrew.SUBCATEGORY_MAP.items():
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
        df = pd.DataFrame(results)
        return df.to_string(index=False)

    @tool("detect_anomalies")
    def detect_anomalies(data: list) -> str:
        """Flag expenses that are statistical outliers (price > mean + 2*std)."""
        if not data:
            return "No data provided."
        df = pd.DataFrame(data)
        if "price" not in df.columns:
            return "No price column found."
        mean = df["price"].mean()
        std = df["price"].std()
        threshold = mean + 2 * std
        anomalies = df[df["price"] > threshold][["id", "purchased", "price", "date", "tags"]]
        if anomalies.empty:
            return "No anomalies detected — all expenses are within normal range."
        return anomalies.to_string(index=False)

    @tool("summarize_patterns")
    def summarize_patterns(data: list) -> str:
        """Identify top spending categories, monthly totals, and budget drift."""
        if not data:
            return "No data provided."
        df = pd.DataFrame(data)
        lines = []

        if "tags" in df.columns and "price" in df.columns:
            top = df.groupby("tags")["price"].sum().sort_values(ascending=False).head(5)
            lines.append("Top spending categories:\n" + top.to_string())

        if "date" in df.columns and "price" in df.columns:
            df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M")
            monthly = df.groupby("month")["price"].sum()
            lines.append("\nMonthly totals:\n" + monthly.to_string())

        return "\n".join(lines) if lines else "Insufficient data for pattern analysis."

    def create_agents(self):
        self.categorizer = Agent(
            role="Expense Categorization Specialist",
            goal=(
                "Assign a precise subcategory to every expense using the classify_expenses tool. "
                "Return a complete, structured list — no expense left as 'Other' if context is available."
            ),
            backstory=(
                "You are a meticulous financial analyst who specializes in classifying personal expenses. "
                "You understand that 'food' can mean a $3 coffee or a $200 dinner party, and you use "
                "every available signal — merchant names, notes, tags, amounts — to assign the right subcategory."
            ),
            tools=[self.classify_expenses],
            verbose=True,
            memory=False,
            llm=self.llm,
            allow_delegation=False,
            cache=True,
        )
        self.pattern_detector = Agent(
            role="Spending Pattern Analyst",
            goal=(
                "Use summarize_patterns to surface meaningful trends and use detect_anomalies to "
                "flag outliers. Combine both into clear, specific findings."
            ),
            backstory=(
                "You are a behavioral finance expert who reads spending data the way a doctor reads "
                "vitals — looking for signals that indicate drift, stress, or opportunity. You never "
                "speculate; every finding maps directly to a data point."
            ),
            tools=[self.summarize_patterns, self.detect_anomalies],
            verbose=True,
            memory=True,
            llm=self.llm,
            max_rpm=10,
            allow_delegation=False,
            cache=True,
        )
        self.advisor = Agent(
            role="Personal Finance Advisor",
            goal=(
                "Synthesize the categorization results and pattern findings into 3-5 specific, "
                "actionable budget recommendations. Each recommendation must name a dollar amount "
                "or percentage target."
            ),
            backstory=(
                "You are a certified financial planner who gives advice based only on data you can see. "
                "You never use vague language like 'spend less on X' — you always quantify: "
                "'Reduce dining out from $340 to $200/month by cooking 3 meals at home per week.'"
            ),
            tools=[],
            verbose=True,
            memory=True,
            llm=self.llm,
            allow_delegation=False,
            cache=True,
        )

    def create_tasks(self):
        self.categorize_task = Task(
            description=(
                f"You have been given a list of expense records.\n\n"
                f"User context: {self.context}\n\n"
                "Use the classify_expenses tool to assign a subcategory to each expense. "
                "Return the full enriched list."
            ),
            expected_output=(
                "A structured table of all expenses with columns: id, purchased, price, "
                "subcategory, original_tags. Every row must have a non-empty subcategory."
            ),
            agent=self.categorizer,
        )
        self.pattern_task = Task(
            description=(
                "Using the expense data:\n"
                "1. Call summarize_patterns to identify top categories and monthly totals.\n"
                "2. Call detect_anomalies to flag outlier transactions.\n"
                "3. List your findings clearly — no speculation."
            ),
            expected_output=(
                "A list of 3-6 findings. Each finding must reference specific numbers from the data. "
                "Include at least one finding about monthly trends and one about anomalies (or explicitly "
                "state that no anomalies were found)."
            ),
            agent=self.pattern_detector,
            context=[self.categorize_task],
        )
        self.advice_task = Task(
            description=(
                "Based on the categorization and pattern findings, write 3-5 specific budget recommendations. "
                "Each recommendation must include a concrete target amount or percentage. "
                "Format as a JSON object matching this schema: "
                '{"summary": str, "key_findings": [str], "anomalies": [str], "recommendations": [str]}'
            ),
            expected_output=(
                'A single JSON object: {"summary": "...", "key_findings": [...], '
                '"anomalies": [...], "recommendations": [...]}'
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
            embedder={
                "provider": "fastembed",
                "config": {"model": "BAAI/bge-small-en-v1.5"},
            },
        )
        result = crew.kickoff(inputs={"data": expenses})
        if hasattr(result, "pydantic") and result.pydantic:
            return result.pydantic.model_dump()
        return {"summary": str(result), "key_findings": [], "anomalies": [], "recommendations": []}