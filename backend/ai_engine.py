import os
import io
import json
import re
from typing import Dict, Any, List, Optional, TypedDict, Tuple
from datetime import datetime

# Import AI SDKs
try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import pypdf
except ImportError:
    pypdf = None

# LangGraph & LangChain imports
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from .database import (
    save_external_disruption, 
    evaluate_disruption_rights,
    get_all_external_disruptions,
    get_all_refund_claims
)
from .travel_retrieval import (
    AviationStackTracker,
    RailRadarTracker,
    GTFSAndBusRetriever,
    get_live_connection_graph_telemetry
)

# Default System Prompt for Voyage Intelligence
SYSTEM_PROMPT = """You are Voyage Intelligence, an advanced autonomous travel resilience concierge and passenger rights advisor.

CRITICAL INSTRUCTIONS:
1. FOCUS DIRECTLY ON THE USER'S QUESTION WITH STRUCTURED, ACTIONABLE ANSWERS:
   - Provide direct, concrete, structured, and helpful answers tailored specifically to what the user asked.
   - DO NOT deflect, stall, or just ask clarifying questions when the user asks for flights, trains, or schedules.
   - DO NOT dump unsolicited programming code (no Python, no bash scripts, no regex tutorials).
   - Keep answers clear, readable, and highly informative with tables, bullet points, and specific details.

2. SCHEDULE, SEARCH & ROUTE QUERIES (MANDATORY STRUCTURED OUTPUT):
   - When the user asks to search, find, or view flights, trains, or buses (e.g. "search flights from Mumbai to Delhi", "27 sep", "look schedule for morning"):
   - ALWAYS PROVIDE A STRUCTURED SCHEDULE TABLE OR DETAILED BREAKDOWN with concrete data:
     * ✈️ Flight / 🚆 Train / 🚌 Bus Code & Operator (e.g., Air India AI 2432, IndiGo 6E 355, Akasa Air QP 1109, Air India Express IX 1050; note: Vistara merged into Air India, UK codes are obsolete)
     * ⏰ Departure & Arrival Times in IST (e.g., Dep: 14:30 IST ➔ Arr: 16:45 IST)
     * ⏱️ Travel Duration & Stops (e.g., 2h 15m Non-stop)
     * 📍 Terminals / Stations (e.g., BOM T2 ➔ DEL T1)
     * 💰 Estimated Price / Fare in INR (e.g., ₹4,500 – ₹5,400 INR)
     * 🛡️ Disruption Risk & Resilience Advice (e.g., Morning flights have lowest ATC delay probability; DGCA CAR Section 3 protection)
   - If the user specifies a time window (e.g. morning, afternoon, evening, night), strictly filter and display flights within that window.
   - Always present concrete flight/train/bus options immediately in the response, even if you ask a follow-up question at the end.

3. TRAVEL DISRUPTION & PASSENGER RIGHTS:
   - When the user asks about flight/train delays, cancellations, or compensation:
     * DGCA CAR Section 3 Series M Part IV (India): Full refund + up to ₹5,000 - ₹10,000 statutory compensation for delays >6 hrs or cancellations without 24hr notice; complimentary refreshments for delays >2 hrs.
     * EU Regulation (EC) 261/2004 & UK261: €250 to €600 compensation for delays >=3 hrs.
     * 2024 U.S. DOT Automatic Cash Refund Mandate: Mandatory prompt cash refund for delays >3 hrs domestic, >6 hrs intl.
     * Indian Railways (IRCTC) TDR: 100% full refund if train is delayed by >3 hrs at boarding point.
   - Propose clear, actionable recovery plans (airline rebooking, Vande Bharat/rail alternative, or road transport).

4. STRICT DOMAIN RESTRICTIONS & BOUNDARIES (MANDATORY):
   - You are exclusively dedicated to travel resilience, flight/train disruptions, tickets, transit, and passenger rights.
   - You are STRICTLY FORBIDDEN from generating code, scripts, math solutions, calculus equations, essays, or answering off-topic non-travel tasks.
   - If asked for non-travel code, math, homework, or general trivia, politely refuse and clarify your travel resilience focus.

Tone: Professional, precise, structured, empathetic, and actionable.
"""

def is_restricted_game_query(query: str) -> bool:
    """
    Detects requests to generate game code or non-travel game scripts.
    Voyage AI is restricted to travel resilience, flight/train disruptions, and passenger rights.
    """
    if not query:
        return False
    q = query.lower()
    
    # Direct game code phrases
    game_code_phrases = [
        "python game", "code of python game", "code for python game",
        "game in python", "game code", "code a game", "write a game",
        "make a game", "create a game", "build a game", "develop a game",
        "snake game", "tic tac toe", "tictactoe", "flappy bird",
        "pong game", "tetris", "pygame", "arcade game", "chess game",
        "hangman game", "rock paper scissors"
    ]
    if any(p in q for p in game_code_phrases):
        return True

    # General check: game keyword + code/programming action
    game_words = ["game", "games", "gaming"]
    code_words = ["code", "script", "program", "write", "develop", "create", "make", "implement", "build"]
    has_game = any(re.search(rf"\b{re.escape(w)}\b", q) for w in game_words)
    has_code = any(re.search(rf"\b{re.escape(w)}\b", q) for w in code_words)

    if has_game and has_code:
        # Exclude legitimate travel contexts
        travel_exceptions = ["connection game", "game theory", "travel simulation", "gamified"]
        if not any(ex in q for ex in travel_exceptions):
            return True

    return False

def is_off_topic_query(query: str) -> Tuple[bool, str]:
    """
    Evaluates if user prompt is outside Voyage AI's travel resilience & passenger rights domain.
    Returns (is_off_topic: bool, category: str).
    Categories: 'code', 'math', 'general'.
    """
    if not query or not isinstance(query, str):
        return False, ""
    
    q = query.lower().strip()
    if not q:
        return False, ""

    # Explicit Travel Context Keywords — if present alongside travel intent, treat as domain inquiry
    travel_explicit_keywords = [
        "flight", "flights", "fight", "flite", "plane", "planes", "airline", "airlines",
        "train", "trains", "rail", "railway", "irctc", "pnr", "ticket", "tickets",
        "booking", "itinerary", "voyage", "dgca", "eu261", "us dot", "tdr", "refund",
        "compensation", "disruption", "delay", "delays", "cancelled", "cancellation",
        "mumbai", "delhi", "bengaluru", "kolkata", "hyderabad", "chennai", "jaipur",
        "terminal", "airport", "station", "platform", "transit", "corridor", "slack",
        "alpine", "zermatt", "london", "zurich", "visp", "sbb", "ba 712", "indigo",
        "air india", "akasa", "vande bharat", "rajdhani", "shatabdi", "seat", "baggage",
        "checkin", "check-in", "boarding", "deboarding", "scheduled", "departure", "arrival", "route"
    ]

    # 1. CODE / PROGRAMMING GENERATION DETECTOR
    code_phrases = [
        "write code", "generate code", "code for", "write a program", "write a script",
        "python code", "java code", "c++ code", "c# code", "javascript code", "typescript code",
        "html code", "css code", "react code", "sql query", "write a function", "write a class",
        "binary search", "bubble sort", "quick sort", "linked list", "fibonacci", "factorial",
        "prime numbers", "snake game", "tic tac toe", "tictactoe", "calculator app",
        "web scraper", "bot script", "python script", "bash script", "powershell script",
        "create a website", "build a website", "develop an app", "coding tutorial",
        "write an algorithm", "solve leetcode", "code in python", "code in java", "code in c++"
    ]
    for cp in code_phrases:
        if cp in q:
            if not any(tk in q for tk in ["travel", "flight", "train", "pnr", "irctc", "dgca", "disruption", "refund", "voyage"]):
                return True, "code"

    # Programming language / term + code / write action verb
    prog_languages = ["python", "java", "c++", "c#", "rust", "golang", "php", "javascript", "typescript", "react", "vue", "angular", "node", "pygame", "html", "css", "sql"]
    action_verbs = ["write", "code", "create", "build", "develop", "implement", "generate", "make", "solve", "script"]
    has_lang = any(re.search(rf"\b{re.escape(pl)}\b", q) for pl in prog_languages)
    has_action = any(re.search(rf"\b{re.escape(av)}\b", q) for av in action_verbs)
    if has_lang and has_action:
        if not any(tk in q for tk in ["travel", "flight", "train", "pnr", "irctc", "dgca", "disruption", "refund", "voyage"]):
            return True, "code"

    # 2. MATHEMATICAL STUFF / EQUATIONS / CALCULUS DETECTOR
    math_phrases = [
        "solve equation", "solve math", "solve calculus", "math problem", "math question",
        "derivative of", "integral of", "calculate equation", "algebra problem",
        "trigonometry", "pythagorean", "quadratic formula", "matrix multiplication",
        "solve 2x", "solve 3x", "solve 4x", "solve 5x", "solve x", "find x in",
        "evaluate expression", "solve expression", "math homework", "calculus problem",
        "differential equation", "linear algebra"
    ]
    for mp in math_phrases:
        if mp in q:
            if not any(tk in q for tk in ["refund", "fare", "delay", "ticket", "cost", "hours", "hrs", "mins", "compensation", "pnr", "slack"]):
                return True, "math"

    # Mathematical calculations / equations regex (e.g. "solve 5x + 10 = 50", "calculate 125 * 45", "what is 250 / 5")
    if re.search(r'\b(solve|calculate|eval|evaluate|compute)\b.*\b(\d+\s*[\+\-\*\/\^\=]\s*\d+|\d*x\s*[\+\-\=])', q):
        if not any(tk in q for tk in ["refund", "fare", "delay", "ticket", "cost", "hours", "hrs", "mins", "compensation", "pnr", "slack", "index"]):
            return True, "math"

    # Simple arithmetic questions (e.g. "what is 15 + 25", "calculate 99 * 3")
    if re.search(r'^(what\s+is|calculate|eval|compute)?\s*\d+\s*[\+\-\*\/]\s*\d+\s*\??$', q):
        if not any(tk in q for tk in ["refund", "fare", "delay", "ticket", "cost", "hours", "hrs", "mins", "compensation", "pnr"]):
            return True, "math"

    # 3. GAME CODE & UNRELATED NON-TRAVEL TASKS
    if is_restricted_game_query(q):
        return True, "code"

    off_topic_tasks = [
        "write an essay", "write a story", "write a poem", "tell me a joke",
        "recipe for", "how to cook", "who won the", "capital of france",
        "who is president", "movie review", "summarize book", "tell me about yourself",
        "write a letter", "generate an article", "write a blog"
    ]
    for ott in off_topic_tasks:
        if ott in q:
            if not any(tk in q for tk in travel_explicit_keywords):
                return True, "general"

    return False, ""

def get_domain_restriction_response(category: str) -> str:
    """
    Returns a clear, polite, structured domain boundary refusal response.
    """
    if category == "code":
        return (
            "### 🛡️ Voyage AI Domain Guard\n\n"
            "I am **Voyage AI**, an autonomous AI concierge dedicated exclusively to **travel disruption resilience, flight & train telemetry, and statutory passenger rights** under DGCA CAR Section 3, EU261, US DOT, and IRCTC.\n\n"
            "I have a **domain restriction** and cannot generate software code, scripts, algorithms, or programming tutorials for non-travel applications.\n\n"
            "#### ✈️ How I can assist you with travel:\n"
            "- **Flight & Train Delay Analytics**: Track live operational status and downstream connection risk.\n"
            "- **Statutory Passenger Rights**: Calculate cash refunds, compensation, and meal entitlements.\n"
            "- **Multi-Modal Recovery Plans**: Recommend alternative air, rail, metro, or road connections.\n\n"
            "*Please let me know if you would like help with an upcoming flight, train, or travel disruption!*"
        )
    elif category == "math":
        return (
            "### 🛡️ Voyage AI Domain Guard\n\n"
            "I am **Voyage AI**, an autonomous AI concierge dedicated exclusively to **travel disruption resilience, flight & train telemetry, and statutory passenger rights**.\n\n"
            "I cannot solve general math homework, algebra, calculus, or scientific equations unrelated to travel.\n\n"
            "#### ✈️ How I can assist you with travel calculations:\n"
            "- **Statutory Compensation**: Calculate mandatory DGCA CAR Section 3 & EU261 cash payouts based on delay hours.\n"
            "- **IRCTC TDR Refund Calculation**: Compute 100% full fare refund eligibility for delayed train journeys.\n"
            "- **Connection Slack Computation**: Evaluate Critical Path Method (CPM) connection windows.\n\n"
            "*Please share your flight or train details to calculate disruption compensation or fare refunds!*"
        )
    else:
        return (
            "### 🛡️ Voyage AI Domain Guard\n\n"
            "I am **Voyage AI**, an autonomous AI concierge dedicated exclusively to **travel disruption resilience, flight & train telemetry, and statutory passenger rights**.\n\n"
            "I cannot assist with general off-topic tasks (such as general essays, non-travel writing, trivia, or non-travel queries).\n\n"
            "#### ✈️ How I can assist you:\n"
            "- **Flight & Train Telemetry**: Search schedules, check live status, and monitor delay risk.\n"
            "- **Passenger Rights & Refunds**: File statutory refund claims under DGCA, IRCTC, EU261, or US DOT.\n"
            "- **Multi-Modal Route Optimization**: Plan backup connections across air, rail, and road.\n\n"
            "*Please let me know how I can help with your travel itinerary!*"
        )

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

class AgentState(TypedDict):
    messages: List[Dict[str, str]]
    user_query: str
    response: Optional[str]
    provider: Optional[str]
    structured_ticket: Optional[Dict[str, Any]]
    live_context: Optional[str]
    error: Optional[str]

def get_groq_keys(custom_key: Optional[str] = None) -> List[str]:
    """Retrieves all configured Groq API keys with support for comma-separated or numbered env vars."""
    keys = []
    if custom_key:
        keys.extend([k.strip() for k in custom_key.split(",") if k.strip()])
    
    # Check GROQ_API_KEYS (comma, space, or newline separated)
    env_multi = os.getenv("GROQ_API_KEYS", "")
    if env_multi:
        keys.extend([k.strip() for k in re.split(r'[,;\n\s]+', env_multi) if k.strip()])
        
    for var in ["GROQ_API_KEY", "GROQ_KEY"]:
        val = os.getenv(var, "").strip()
        if val:
            keys.extend([k.strip() for k in val.split(",") if k.strip()])
            
    for i in range(1, 10):
        val = os.getenv(f"GROQ_API_KEY_{i}", "").strip()
        if val:
            keys.append(val)
            
    seen = set()
    uniq = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            uniq.append(k)
    return uniq

def get_gemini_keys(custom_key: Optional[str] = None) -> List[str]:
    """Retrieves all configured Gemini API keys with support for comma-separated or numbered env vars."""
    keys = []
    if custom_key:
        keys.extend([k.strip() for k in custom_key.split(",") if k.strip()])
        
    env_multi = os.getenv("GEMINI_API_KEYS", "")
    if env_multi:
        keys.extend([k.strip() for k in re.split(r'[,;\n\s]+', env_multi) if k.strip()])
        
    for var in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
        val = os.getenv(var, "").strip()
        if val:
            keys.extend([k.strip() for k in val.split(",") if k.strip()])
            
    for i in range(1, 10):
        val = os.getenv(f"GEMINI_API_KEY_{i}", "").strip()
        if val:
            keys.append(val)
            
    seen = set()
    uniq = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            uniq.append(k)
    return uniq

def get_groq_key(custom_key: Optional[str] = None) -> Optional[str]:
    keys = get_groq_keys(custom_key)
    return keys[0] if keys else None

def get_gemini_key(custom_key: Optional[str] = None) -> Optional[str]:
    keys = get_gemini_keys(custom_key)
    return keys[0] if keys else None

def get_system_prompt_with_ticket(state: AgentState) -> str:
    prompt = SYSTEM_PROMPT
    if state.get("live_context"):
        prompt += f"\n\n{state['live_context']}"
    if state.get("structured_ticket"):
        st = state["structured_ticket"]
        is_past = bool(st.get("is_past_journey", False))
        travel_dt = st.get("travel_date", "")
        delay_m = st.get("delay_minutes", 0)
        pax_name = st.get("passenger_name") or "Passenger"
        cost_val = st.get("ticket_cost")
        fare_str = f"₹{float(cost_val):,.2f} {st.get('currency', 'INR')}" if (cost_val is not None and float(cost_val) > 0) else "Standard Fare"
        
        # Exact departure & arrival time resolution
        srv_str = str(st.get('service_number', ''))
        orig_str = str(st.get('origin', ''))
        dest_str = str(st.get('destination', ''))
        if "15088" in srv_str or ("panvel" in orig_str.lower() and "csmt" in dest_str.lower()):
            sched_dep = st.get("scheduled_departure") or "05:35 IST"
            sched_arr = st.get("scheduled_arrival") or "06:45 IST"
        else:
            sched_dep = st.get("scheduled_departure") or "15:30 IST"
            sched_arr = st.get("scheduled_arrival") or "17:50 IST"

        # Check if the arrival time has already passed
        now = datetime.now()
        has_arrived = is_past or st.get("journey_status") == "COMPLETED"
        if not has_arrived:
            try:
                arr_clean = re.sub(r'[^0-9:]', '', str(sched_arr).split()[0])
                arr_parts = arr_clean.split(":")
                if len(arr_parts) >= 2:
                    arr_h = int(arr_parts[0])
                    arr_m = int(arr_parts[1])
                    today_str = now.strftime("%Y-%m-%d")
                    t_str = str(travel_dt).strip()
                    if t_str <= today_str or "2024" in t_str or "2025" in t_str or now.strftime("%d-%b-%Y").lower() in t_str.lower():
                        if now.hour > arr_h or (now.hour == arr_h and now.minute >= arr_m):
                            has_arrived = True
            except Exception:
                pass

        current_time_str = now.strftime("%d-%b-%Y %I:%M %p IST")

        prompt += (
            f"\n\nCURRENT PASSENGER TICKET CONTEXT:\n"
            f"- Passenger Name: {pax_name}\n"
            f"- Carrier & Service: {st.get('carrier')} {st.get('service_number')}\n"
            f"- Route: {st.get('origin')} to {st.get('destination')}\n"
            f"- Travel Date: {travel_dt or 'Recent'}\n"
            f"- Scheduled Departure Time: {sched_dep}\n"
            f"- Scheduled Arrival Time: {sched_arr}\n"
            f"- Current Clock Time: {current_time_str}\n"
            f"- Has Service Already Arrived: {'YES - TRAIN HAS ALREADY REACHED DESTINATION AT ' + sched_arr if has_arrived else 'NO - Upcoming / En Route'}\n"
            f"- Delay: +{delay_m} mins\n"
            f"- Status: {'Cancelled' if st.get('is_cancellation') else ('Completed Run (Already Arrived)' if has_arrived else ('Delayed' if delay_m > 0 else 'On Schedule'))}\n"
            f"- PNR: {st.get('pnr')}\n"
            f"- Fare: {fare_str}\n"
            f"- Reason: {st.get('disruption_reason')}"
        )
        if has_arrived:
            prompt += f"\nCRITICAL INSTRUCTION: This train/service has ALREADY REACHED {st.get('destination')} at {sched_arr}. If the user asks when it reaches or if it has reached, state explicitly and directly that it ALREADY ARRIVED at {sched_arr} (on {travel_dt}). Do NOT claim it is currently running on schedule in the future."
        else:
            prompt += f"\nCRITICAL INSTRUCTION: When the user asks when they will reach or arrive at {st.get('destination')}, state the EXACT scheduled arrival time: {sched_arr} (Expected Arrival: {sched_arr}, current delay: +{delay_m} mins). Always provide the concrete clock time."
    return prompt


def call_groq(state: AgentState, groq_key: str) -> AgentState:
    """Attempts generation via Groq API with robust model fallback."""
    try:
        client = Groq(api_key=groq_key)
        sys_prompt = get_system_prompt_with_ticket(state)
        formatted_messages = [{"role": "system", "content": sys_prompt}]
        for m in state["messages"]:
            formatted_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        if state["user_query"] and (not state["messages"] or state["messages"][-1].get("content") != state["user_query"]):
            formatted_messages.append({"role": "user", "content": state["user_query"]})

        # Priority requested by user:
        # 1. llama-3.3-70b-versatile
        # 2. llama-3.1-8b-instant
        # 3. other available models (qwen/qwen3.8-27b, openai/gpt-oss-20b, openai/gpt-oss-120b)
        candidate_models = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-20b",
            "openai/gpt-oss-120b",
        ]

        last_err = None
        for model_name in candidate_models:
            try:
                completion = client.chat.completions.create(
                    model=model_name,
                    messages=formatted_messages,
                    temperature=0.4,
                    max_tokens=2048,
                    timeout=20.0
                )
                reply = completion.choices[0].message.content
                if reply and reply.strip():
                    state["response"] = reply
                    state["provider"] = "Voyage AI Engine"
                    return state
            except Exception as me:
                last_err = me
                continue

        state["error"] = f"Groq all models failed: {str(last_err)}"
        return state
    except Exception as e:
        state["error"] = f"Groq error: {str(e)}"
        return state

def call_gemini(state: AgentState, gemini_key: str) -> AgentState:
    """Attempts generation via Google Gemini API with robust model fallback."""
    try:
        genai.configure(api_key=gemini_key)
        # Priority: cheapest Gemini models first (Sep 2026 pricing)
        # gemini-3.1-flash-lite: ~$0.25/$1.50 per 1M tokens (cheapest)
        # gemini-3.5-flash-lite: ~$0.30/$2.50 per 1M tokens
        # gemini-2.5-flash-lite: budget tier
        # gemini-2.5-flash: stable fallback
        candidate_models = [
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
        ]

        # Build chat history safely, ensuring alternating user/model roles
        chat_history = []
        if state["messages"] and len(state["messages"]) > 1:
            for m in state["messages"][:-1]:
                role = "model" if m.get("role") in ["assistant", "model", "bot"] else "user"
                content = m.get("content", "")
                if not content:
                    continue
                # Ensure alternating roles (Gemini API requirement)
                if chat_history and chat_history[-1]["role"] == role:
                    # Merge consecutive same-role messages
                    chat_history[-1]["parts"][0] += "\n" + content
                else:
                    chat_history.append({"role": role, "parts": [content]})
        
        query = state["user_query"] or (state["messages"][-1]["content"] if state["messages"] else "Hello")
        sys_prompt = get_system_prompt_with_ticket(state)

        last_err = None
        for model_name in candidate_models:
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=sys_prompt
                )
                if chat_history:
                    chat = model.start_chat(history=chat_history)
                    response = chat.send_message(query)
                else:
                    response = model.generate_content(query)
                if response and response.text and response.text.strip():
                    state["response"] = response.text
                    state["provider"] = "Voyage AI Engine"
                    return state
            except Exception as me:
                last_err = me
                continue

        state["error"] = f"Gemini all models failed: {str(last_err)}"
        return state
    except Exception as e:
        state["error"] = f"Gemini error: {str(e)}"
        return state

def extract_route_pair(q_text: str) -> tuple[str, str]:
    """Extract origin and destination city or airport names from user query."""
    m = re.search(r'(?:from|between)\s+([a-zA-Z\s]+?)\s+(?:to|and)\s+([a-zA-Z\s]+)', q_text, re.IGNORECASE)
    if not m:
        m = re.search(r'([a-zA-Z\s]+?)\s+to\s+([a-zA-Z\s]+)', q_text, re.IGNORECASE)
    if m:
        o_raw = m.group(1).strip()
        d_raw = m.group(2).strip()
        clean_pattern = r'^(?:can\s+you\s+)?(?:please\s+)?(?:give|show|tell|find|search|check|get|me|info|information|details|about|tickets?|schedule|status|flights?|fights?|trains?|buses?|travels?|options?|for|the|cheap|cheapest|any)\s+'
        o_clean = re.sub(clean_pattern, '', o_raw, flags=re.IGNORECASE).strip().title()
        d_clean = re.sub(r'\s+(?:flights?|fights?|trains?|buses?|travels?|options?|details?|tickets?|today|tomorrow|now|please)$', '', d_raw, flags=re.IGNORECASE).strip().title()
        if len(o_clean) >= 2 and len(d_clean) >= 2 and o_clean.lower() != d_clean.lower():
            return o_clean, d_clean
    return "", ""

def call_expert_engine(state: AgentState) -> AgentState:
    """High-intelligence local fallback that understands travel laws and extracts disruptions."""
    query = state["user_query"].strip()
    lower = query.lower()

    is_off_topic, category = is_off_topic_query(query)
    if is_off_topic:
        state["response"] = get_domain_restriction_response(category)
        state["provider"] = "Voyage Domain Guard"
        return state
    # Case 0a: User asks about refund claims / dispute status
    if any(k in lower for k in ["claim", "claims", "refund claim", "filed claim", "claim receipt", "dispute", "claim status"]):
        db_claims = get_all_refund_claims()
        if db_claims:
            claim_rows = []
            for c in db_claims:
                c_amt = float(c.get('claimed_amount', 0) or 0)
                claim_rows.append(
                    f"| **{c.get('claim_id')}** | `{c.get('pnr')}` | {c.get('passenger_name')} | {c.get('airline')} | ₹{c_amt:,.2f} INR | **{c.get('claim_status')}** | {str(c.get('filing_timestamp', ''))[:16]} |"
                )
            reply = f"""### 🛡️ Verified Refund & Dispute Claims Ledger

Here are your authentic statutory refund claims recorded in the Voyage Disruption Ledger:

| Claim ID | PNR | Passenger | Carrier | Claimed Amount | Status | Filed Date |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
""" + "\n".join(claim_rows) + """

---
#### 📋 Next Steps:
• All claims are digitally filed under statutory frameworks (DGCA CAR Section 3 / IRCTC TDR Regulations).
• Carriers are legally mandated to process cash refunds within 7 business days directly to the original payment mode.
"""
            state["response"] = reply
            state["provider"] = "voyage_claims_ledger"
            return state
        else:
            reply = """### 🛡️ Statutory Refund Claims Status

No refund claims have been filed yet for your itinerary. 

If your train is delayed by **>3 hours** at your boarding station or your flight is delayed by **>6 hours / cancelled**, you are entitled to a **100% full statutory refund**. Click **"File Claim"** or upload your ticket to begin."""
            state["response"] = reply
            state["provider"] = "voyage_claims_ledger"
            return state

    # Case 0b: Explicit trip summary / itinerary query
    explicit_trip_summary_keywords = [
        "my trip", "my journey", "my ticket", "my tickets", "my itinerary",
        "trip summary", "journey summary", "trip details", "itinerary summary",
        "show my ticket", "show my tickets", "show my booking", "view my booking",
        "what is my itinerary", "what are my trip details", "summary of my trip",
        "show itinerary", "view itinerary", "itinerary details", "my travel details"
    ]
    is_trip_summary_query = any(phrase in lower for phrase in explicit_trip_summary_keywords) or query.lower().strip() in ["my trip", "itinerary", "my tickets", "trip details", "trip summary", "show trip"]

    active_t = state.get("structured_ticket")
    all_ext_tickets = get_all_external_disruptions()
    if not active_t and all_ext_tickets:
        active_t = all_ext_tickets[0]
        state["structured_ticket"] = active_t

    if is_trip_summary_query and (active_t or all_ext_tickets):
        # Deduplicate tickets by PNR and service_number
        unique_tickets = []
        seen_keys = set()
        for t in all_ext_tickets:
            k = f"{t.get('pnr', '')}_{t.get('service_number', '')}"
            if k not in seen_keys:
                seen_keys.add(k)
                unique_tickets.append(t)

        is_specific_single = active_t and any(str(active_t.get("service_number", "")).lower() in lower or str(active_t.get("pnr", "")).lower() in lower)
        if len(unique_tickets) > 1 and not is_specific_single:
            leg_items = []
            for idx, t in enumerate(unique_tickets, 1):
                del_m = int(t.get("delay_minutes", 0) or 0)
                del_txt = f"+{del_m}m delay" if del_m > 0 else "Running Right Time (On-Time)"
                t_fare = float(t.get("ticket_cost", 0) or 0)
                fare_txt = f"₹{t_fare:,.2f} INR" if t_fare > 0 else "Standard Fare"
                pax_n = t.get("passenger_name") or "Passenger"
                is_past_leg = bool(t.get("is_past_journey"))
                leg_items.append(
                    f"• **Leg {idx}**: **{t.get('carrier')} #{t.get('service_number')}**\n"
                    f"  - Route: **{t.get('origin')} ➔ {t.get('destination')}** (PNR: `{t.get('pnr')}`)\n"
                    f"  - Travel Date: {t.get('travel_date', 'Recent')} | Status: **{del_txt}**{' (Completed Run)' if is_past_leg else ''}\n"
                    f"  - Passenger: {pax_n} | Fare: {fare_txt}"
                )
            
            c_orig = unique_tickets[0].get("origin", "Origin")
            c_dest = unique_tickets[-1].get("destination", "Destination")
            reply = f"""### 🗺️ Multi-Modal Connected Journey Itinerary

You have **{len(unique_tickets)} connected travel documents** recorded in your Voyage ledger:

""" + "\n\n".join(leg_items) + f"""

---

#### 🛡️ Critical Path & Passenger Rights:
• **Full Corridor**: **{c_orig} ➔ ... ➔ {c_dest}**
• **Interchange Protection**: Topological connection slack calculated via Critical Path Method (CPM).
• **Statutory Protection**: IRCTC TDR Regulations active across rail segments; DGCA CAR Section 3 active across air legs.

Choose an action below to view the interactive connection map, chat about specific legs, or upload additional vouchers."""
            state["response"] = reply
            state["provider"] = "voyage_trip_expert"
            return state

        # Single active ticket summary
        if active_t:
            carrier = active_t.get("carrier", "Carrier")
            service = active_t.get("service_number", "Transit Link")
            orig = active_t.get("origin", "Origin")
            dest = active_t.get("destination", "Destination")
            delay_m = int(active_t.get("delay_minutes", 0) or 0)
            pnr = active_t.get("pnr", "N/A")
            raw_cost = active_t.get("ticket_cost")
            fare = float(raw_cost) if (raw_cost is not None and float(raw_cost) > 0) else 0.0
            curr = active_t.get("currency", "INR")
            reason = active_t.get("disruption_reason", "Nominal on-schedule operation")
            is_canc = bool(active_t.get("is_cancellation", False))
            is_past = bool(active_t.get("is_past_journey", False))
            travel_dt = active_t.get("travel_date", "")
            pax = active_t.get("passenger_name") or "Passenger"
            fare_display = f"₹{fare:,.2f} {curr}" if fare > 0 else "Standard Fare"

            rights = evaluate_disruption_rights(carrier, delay_m, is_canc, fare)

            if is_past:
                reply = f"""### 🚆 Historical Journey Record (Completed Service)

This travel document is for **{carrier} {service}** ({orig} ➔ {dest}) scheduled on **{travel_dt or 'a previous date'}**.

• **Passenger**: **{pax}**
• **Service Run Status**: **ALREADY COMPLETED**. This train/service has completed its scheduled journey and is **no longer currently running**.
• **Route Corridor**: **{orig} ➔ {dest}** (PNR: `{pnr}`)
• **Scheduled Departure**: Completed as scheduled.
• **Recorded Fare**: {fare_display}

---

#### ❓ Did you catch this train or miss it?
• **If you caught & boarded the train**:
  Your journey has already been completed. No further action is required unless the train arrived with an operational delay exceeding 3 hours and you wish to file a customer grievance.

• **If you missed the train**:
  Under Indian Railways / IRCTC rules:
  1. You can file an **online TDR (Ticket Deposit Receipt)** on the IRCTC portal under reason code *"Passenger Not Travelled"* or *"Train Running Late > 3 Hours"*.
  2. TDR filing window: Must be filed before or within statutory IRCTC timelines (within 72 hours of chart preparation depending on the reason).
  3. If eligible, IRCTC will process a statutory refund after verification by the train ticket examiner (TTE) charting system.

Feel free to ask any specific questions about your rights or refund options!"""
            else:
                reply = f"""### ✈️ Trip Details & Resilience Status

Here is the authentic summary of your trip for **{carrier} {service}**:

• **Passenger**: **{pax}**
• **Route Corridor**: **{orig} ➔ {dest}**
• **Booking Reference / PNR**: `{pnr}`
• **Current Status**: **{"+ " + str(delay_m) + " minutes delay" if delay_m > 0 else "On Schedule (Running Right Time)"}** {"(Service Cancelled)" if is_canc else ""}
• **Disruption Reason**: {reason}
• **Total Ticket Fare**: {fare_display}

---

#### 🛡️ Statutory Passenger Rights & Protection:
• **Governing Framework**: {rights['applicable_law']}
• **Full Fare Refund**: {"Eligible (100% refund without cancellation deductions)" if rights['refund_eligible'] else "Standard carrier refund policy"}
• **Direct Statutory Compensation**: **₹{rights['statutory_compensation']:,.2f} INR**
• **Duty of Care**: Mandatory refreshments/meals at departure terminal during delays exceeding 2 hours.

#### 🗺️ Next Steps & Recovery:
- Click **Upload Another** if you have a connecting flight, train, or hotel voucher to analyze.
- Click **Done (View Map)** to inspect your trip on the Google Maps visualizer and view recovery plans."""
            state["response"] = reply
            state["provider"] = "voyage_trip_expert"
            return state

    # Case 0d: Inquiries about arrival time / reaching destination (e.g. "when reach csmt", "when will i reach", "arrival time", "did it reach", "has it arrived")
    arrival_query_keywords = [
        "when reach", "when will i reach", "when do we reach", "when does it reach",
        "what time reach", "what time will i reach", "arrival time", "when arrive",
        "when will it arrive", "when will i arrive", "what time arrive", "did it reach",
        "has it reached", "has it arrived", "reach csmt", "arrive at", "time of arrival",
        "when we reach", "timing of arrival", "arrival timing", "when i reach"
    ]
    is_arrival_query = any(k in lower for k in arrival_query_keywords) or (("reach" in lower or "arrive" in lower) and any(h in lower for h in ["csmt", "pnvl", "mumbai", "delhi", "ndls", "jai", "station", "airport", "terminal", "dest"]))
    if is_arrival_query and (active_t or all_ext_tickets):
        t_rec = active_t or all_ext_tickets[0]
        c_name = t_rec.get("carrier") or "Carrier"
        s_num = t_rec.get("service_number") or "Service"
        orig_s = t_rec.get("origin") or "Origin"
        dest_s = t_rec.get("destination") or "Destination"
        pnr_s = t_rec.get("pnr") or "N/A"
        delay_val = int(t_rec.get("delay_minutes", 0) or 0)
        t_date = t_rec.get("travel_date") or datetime.now().strftime("%d-%b-%Y")
        
        if "15088" in str(s_num) or ("panvel" in orig_s.lower() and "csmt" in dest_s.lower()):
            s_dep = t_rec.get("scheduled_departure") or "05:35 IST"
            s_arr = t_rec.get("scheduled_arrival") or "06:45 IST"
        else:
            s_dep = t_rec.get("scheduled_departure") or "15:30 IST"
            s_arr = t_rec.get("scheduled_arrival") or "17:50 IST"

        # Check if the arrival has passed
        now = datetime.now()
        has_arrived = bool(t_rec.get("is_past_journey")) or t_rec.get("journey_status") == "COMPLETED"
        if not has_arrived:
            try:
                arr_clean = re.sub(r'[^0-9:]', '', str(s_arr).split()[0])
                arr_parts = arr_clean.split(":")
                if len(arr_parts) >= 2:
                    arr_h = int(arr_parts[0])
                    arr_m = int(arr_parts[1])
                    today_str = now.strftime("%Y-%m-%d")
                    t_str = str(t_date).strip()
                    if t_str <= today_str or "2024" in t_str or "2025" in t_str or now.strftime("%d-%b-%Y").lower() in t_str.lower():
                        if now.hour > arr_h or (now.hour == arr_h and now.minute >= arr_m):
                            has_arrived = True
            except Exception:
                pass

        if has_arrived:
            reply = f"""### 🚆 Train Has Already Arrived at {dest_s}

• **Train / Service**: **{c_name} {s_num}**
• **Route Corridor**: **{orig_s} ➔ {dest_s}**
• **Scheduled Arrival Time**: **{s_arr}**
• **Travel Date**: **{t_date}**
• **Current Status**: ✅ **ALREADY REACHED / JOURNEY COMPLETED**
• **PNR**: `{pnr_s}`

---
#### 📍 Journey Status Summary:
Your train was scheduled to arrive at **{dest_s}** at **{s_arr}**. Because the current time is past the scheduled arrival, this service has **already arrived at the terminal and completed its run**.

• If you traveled on this service, no further action is required.
• If you missed this train or it suffered a delay exceeding 3 hours, you can file an online IRCTC TDR (Ticket Deposit Receipt) for a statutory refund."""
        else:
            delay_text = f"+{delay_val}m delay" if delay_val > 0 else "Running Right Time (On Schedule)"
            reply = f"""### 🚆 Scheduled Arrival Information

• **Train / Service**: **{c_name} {s_num}**
• **Route Corridor**: **{orig_s} ➔ {dest_s}**
• **Scheduled Departure**: **{s_dep}** from {orig_s}
• **Scheduled Arrival Time**: **{s_arr}** at **{dest_s}**
• **Current Operating Status**: **{delay_text}**
• **Expected Arrival Time**: **{s_arr}** (Expected on schedule)
• **PNR**: `{pnr_s}`

---
*Tip: Deboarding platforms at major terminals can be busy. Allow 10–15 minutes for deboarding and station exit.*"""

        state["response"] = reply
        state["provider"] = "voyage_arrival_tracker"
        return state

    # Case 1: User asks to write code
    if any(k in lower for k in ["write code", "code for", "create a website", "react component", "html", "javascript", "python", "fastapi"]):
        if "website" in lower or "travel" in lower or "booking" in lower or "disruption" in lower:
            state["response"] = """### 🚀 Production Travel Disruption Resolver Component (React + Tailwind)

Here is a complete, self-contained interactive component that handles travel disruption monitoring, topological slack computation, and passenger rights claim filing:

```jsx
import React, { useState } from 'react';
import { ShieldCheck, AlertTriangle, ArrowRight, Zap, RefreshCw } from 'lucide-react';

export default function TravelRecoveryWidget({ pnr = "VY-8820", initialDelay = 195 }) {
  const [delayMins, setDelayMins] = useState(initialDelay);
  const [claimFiled, setClaimFiled] = useState(false);
  const isEligible = delayMins >= 180;

  const handleClaim = () => {
    setClaimFiled(true);
  };

  return (
    <div className="max-w-xl mx-auto p-6 rounded-3xl bg-white border border-slate-200 shadow-md font-sans">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-mono font-bold text-slate-500">VOYAGE AUTONOMOUS SOLVER</span>
        </div>
        <span className="text-xs font-mono text-slate-400">PNR: {pnr}</span>
      </div>

      <div className="mt-4 space-y-3">
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <div className="font-bold text-sm text-amber-900">
              Disruption Detected (+{delayMins} min delay)
            </div>
            <p className="text-xs text-amber-800 mt-0.5">
              Downstream transfer window reduced below Minimum Connection Time (MCT).
            </p>
          </div>
        </div>

        {isEligible && (
          <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 space-y-1">
            <div className="font-bold flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>DGCA CAR Section 3 & EU261 Protection Active</span>
            </div>
            <p>100% Full Fare Refund Eligible + ₹5,000 Statutory Delay Compensation.</p>
          </div>
        )}

        <div className="pt-2 flex items-center justify-between gap-3">
          <button
            onClick={() => setDelayMins(prev => prev + 30)}
            className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition"
          >
            +30m Delay
          </button>
          
          <button
            onClick={handleClaim}
            disabled={claimFiled}
            className="flex-1 py-2.5 rounded-xl text-xs font-bold text-white bg-[#181E4B] hover:bg-[#232a68] shadow transition flex items-center justify-center gap-1.5"
          >
            {claimFiled ? "Claim Submitted (ACK-VY-9940)" : "1-Click File Refund Claim"}
            {!claimFiled && <ArrowRight className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}
```

#### How It Works:
- **Real-time Slack Monitoring**: Computes whether the delay margin breaches Minimum Connection Times.
- **Automated Legal Compliance**: Directly checks DGCA CAR Section 3 and EU261 thresholds.
- **1-Click Settlement**: Submits the claim with instant cryptographic acknowledgement.
"""
        else:
            state["response"] = f"""Here is a clean implementation for your request:

```python
# Voyage Automated Disruption Resolver Engine
import json
from datetime import datetime

def evaluate_disruption_claim(airline: str, delay_minutes: int, ticket_cost: float) -> dict:
    \"\"\"
    Enforces statutory passenger rights under DGCA CAR Section 3 (India).
    \"\"\"
    eligible = delay_minutes >= 180
    refund_fare = ticket_cost if delay_minutes >= 360 else (ticket_cost * 0.5 if eligible else 0.0)
    statutory_comp = 5000.0 if delay_minutes >= 360 else (3000.0 if eligible else 0.0)

    return {{
        "airline": airline,
        "delay_minutes": delay_minutes,
        "statutory_eligible": eligible,
        "refund_amount": refund_fare,
        "statutory_compensation": statutory_comp,
        "total_claim": refund_fare + statutory_comp,
        "filing_status": "READY_TO_LODGE"
    }}

# Example usage:
claim = evaluate_disruption_claim("IndiGo", 210, 6450.0)
print(json.dumps(claim, indent=2))
```
"""
        state["provider"] = "voyage_code_agent"
        return state

    # Case 2: Flight Queries (Specific Flight Code OR Route Queries like Mumbai to Delhi)
    flight_keywords = ["flight", "flights", "fight", "flite", "fly", "flying", "plane", "planes", "airline", "airlines", "airways", "aviation", "aviationstack", "airfare"]
    is_flight_query = any(k in lower for k in flight_keywords)

    if is_flight_query or any(k in lower for k in ["ai 882", "ai882", "6e 521", "6e521", "track flight", "flight status"]):
        # Check if user mentioned a specific flight code
        flight_code_match = re.search(r'\b([A-Z0-9]{2}\s?\d{3,4})\b', query.upper())
        # Filter out common false positives for flight codes
        if flight_code_match and flight_code_match.group(1) not in ["TO", "ME", "IN", "IS", "ON", "AT"]:
            flight_code = flight_code_match.group(1)
            flight_tracker = AviationStackTracker()
            f_data = flight_tracker.get_flight_status(flight_code)
            delay_text = f"+{f_data['delay_minutes']} min delay" if f_data.get('delay_minutes', 0) > 0 else "On Schedule"
            reply = f"""### ✈️ Flight Radar Telemetry :: {f_data.get('flight_iata', flight_code)}

- **Carrier**: {f_data.get('airline', 'Scheduled Airline')}
- **Route**: {f_data.get('departure_airport', 'Departure')} ({f_data.get('departure_iata', '')}) ➔ {f_data.get('arrival_airport', 'Arrival')} ({f_data.get('arrival_iata', '')})
- **Status**: **{f_data.get('status', 'scheduled').upper()}** ({delay_text})
- **Departure Terminal / Gate**: {f_data.get('departure_terminal', 'TBD')} / **{f_data.get('departure_gate', 'TBD')}**
- **Scheduled Departure**: {f_data.get('scheduled_departure', 'Consult airline')}
- **Estimated Arrival**: {f_data.get('estimated_arrival', 'Consult airline')}
- **Aircraft Equipment**: {f_data.get('aircraft', 'Commercial Jet')}
- **Passenger Rights Notice**: Delays > 2 hours entitle passengers to free refreshments under DGCA CAR Section 3. Delays > 6 hours or cancellations qualify for 100% full refund + statutory compensation up to ₹5,000–₹10,000.
"""
            state["response"] = reply
            state["provider"] = "aviationstack_flight_tracker"
            return state

        # If it's a route flight query (e.g. "flights from Mumbai to Delhi")
        orig_f, dest_f = extract_route_pair(query)
        if not orig_f or not dest_f:
            if "mumbai" in lower and "delhi" in lower:
                orig_f, dest_f = "Mumbai", "Delhi"
            elif "bangalore" in lower or "blr" in lower:
                orig_f, dest_f = "Bangalore", "Delhi"
            elif "mumbai" in lower and "goa" in lower:
                orig_f, dest_f = "Mumbai", "Goa"
            elif "delhi" in lower and "jaipur" in lower:
                orig_f, dest_f = "Delhi", "Jaipur"
            else:
                orig_f, dest_f = "Mumbai", "Delhi"

        o_loc = lookup_location(orig_f)
        d_loc = lookup_location(dest_f)
        dep_c = o_loc["code"] if o_loc else orig_f[:3].upper()
        arr_c = d_loc["code"] if d_loc else dest_f[:3].upper()

        flight_tracker = AviationStackTracker()
        r_flights = flight_tracker.search_route_flights(dep_iata=dep_c, arr_iata=arr_c)
        if r_flights:
            fl_rows = []
            for rf in r_flights:
                fl_rows.append(
                    f"| {rf['departure_time']} | **{rf['flight_iata']}** | {rf['airline']} | {rf['departure_iata']} ({rf['departure_terminal']}) ➔ {rf['arrival_iata']} ({rf['arrival_terminal']}) | {rf['duration']} | ₹{rf['estimated_fare_inr']:,} INR | {rf['status'].upper()} |"
                )
            tbl = "\n".join(fl_rows)
            reply = f"""### ✈️ Real-Time Flight Radar Schedule :: {orig_f} ({dep_c}) ➔ {dest_f} ({arr_c})

| Departure (IST) | Flight | Airline | Route / Terminals | Duration | Est. Fare | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{tbl}

---

#### 🛡️ DGCA Statutory Passenger Protections (CAR Section 3 Series M Part IV):
• **Delays Exceeding 2 Hours**: Airline must provide complimentary refreshments and meals at the departure terminal.
• **Delays Exceeding 6 Hours or Cancellations**: Mandatory 100% full cash refund with zero deduction OR immediate alternative flight rebooking, plus statutory compensation up to ₹5,000–₹10,000.
• **ATC Resilience**: Morning departures enjoy significantly lower turnaround delay risk compared to late afternoon bank arrivals.
"""
            state["response"] = reply
            state["provider"] = "aviationstack_flight_tracker"
            return state

        reply = f"""### ✈️ Flight Corridor Intelligence :: {orig_f} ➔ {dest_f}

Real-time flight schedule between **{orig_f}** and **{dest_f}**:
• Operating Airlines: **IndiGo, Air India, Akasa Air, Air India Express, and SpiceJet**.
• Flight Duration: Approximately **2 hours to 2 hours 15 minutes** (non-stop).
• Under DGCA CAR Section 3, delays > 2 hours entitle passengers to free refreshments; delays > 6 hours qualify for 100% full cash refund."""
        state["response"] = reply
        state["provider"] = "voyage_flight_expert"
        return state

    # Case 3: Train Running Status / RailRadar Tool & Route Queries
    train_keywords = ["train", "trains", "rail", "railway", "railradar", "irctc", "vande bharat", "rajdhani", "shatabdi", "duronto", "tejas", "mail", "express", "tdr"]
    train_match = re.search(r'\b([012]\d{4})\b', query)
    is_train_query = bool(train_match) or any(k in lower for k in train_keywords)

    if is_train_query:
        if train_match or any(k in lower for k in ["12134", "12810", "20978", "12951"]):
            train_num = train_match.group(1) if train_match else ("12810" if "12810" in lower else ("20978" if "vande" in lower or "20978" in lower else ("12951" if "rajdhani" in lower else "12134")))
            t_data = RailRadarTracker.get_live_train_status(train_num)
            delay_val = t_data.get('delay_minutes', 0)
            delay_str = f"+{delay_val} mins delay" if delay_val > 0 else "Running Right Time (On-Time)"
            
            reply = f"""### 🚆 RailRadar Live Train Tracker :: {t_data.get('train_name', f'Train #{train_num}')}

• **Service**: #{t_data.get('train_number', train_num)} {t_data.get('train_name', 'Express')}
• **Route Corridor**: **{t_data.get('origin', 'Origin')} ➔ {t_data.get('destination', 'Destination')}**
• **Status**: **{t_data.get('status', 'running').upper()}** ({delay_str})
• **Live Current Location**: Currently approaching/at **{t_data.get('current_location', 'In transit')}**
• **Next Station / Halt**: **{t_data.get('upcoming_station', 'In transit')}**
• **Previous Station**: {t_data.get('prev_station', 'N/A')}
• **Live GPS Telemetry**: Distance Remaining: {t_data.get('distance_remaining_km', 0)} km | Avg Speed: {t_data.get('avg_speed_kmh', 0)} km/h
• **IRCTC TDR Status**: {"100% Full Fare Refund Eligible (Delay exceeds 3 hours)" if t_data.get('tdr_refund_eligible') else "Nominal Schedule (Zero Cancellation Penalty under Normal Rules)"}
• **Data Engine**: *RailRadar Live Indian Railways API v1 (api.railradar.in)*
"""
            state["response"] = reply
            state["provider"] = "railradar_train_tracker"
            return state

        # If it's a route train query (e.g. "train from Mumbai to Delhi")
        orig_t, dest_t = extract_route_pair(query)
        if not orig_t or not dest_t:
            orig_t, dest_t = ("Mumbai", "Delhi") if ("mumbai" in lower and "delhi" in lower) else ("Mumbai", "Delhi")

        live_trains = RailRadarTracker.search_route_trains(orig_t, dest_t)
        if live_trains:
            tr_rows = []
            for tr in live_trains:
                del_val = tr.get("delay_minutes", 0)
                del_str = f"+{del_val} mins delay" if del_val > 0 else "Running Right Time (On-Time)"
                tr_rows.append(
                    f"| **#{tr['train_number']}** | {tr['train_name']} | **{tr['status'].upper()}** | {tr.get('current_location', 'In transit')} | {tr.get('upcoming_station', 'En route')} | {del_str} | {'100% Refund Eligible' if tr.get('tdr_refund_eligible') else 'Normal'} |"
                )
            tbl = "\n".join(tr_rows)
            reply = f"""### 🚆 RailRadar Live Indian Railways Telemetry :: {orig_t} ➔ {dest_t}

| Train # | Service Name | Status | Current Location | Next Station | Delay | IRCTC TDR |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{tbl}

---

#### 🛡️ IRCTC Passenger Refund Rules (TDR):
• **Delay Exceeding 3 Hours**: If your train is delayed by more than 3 hours at your boarding station and you choose not to travel, you are legally entitled to a **100% full fare refund with zero cancellation deduction** by filing an online TDR before train departure.
• **Live Telemetry Engine**: RailRadar Live Indian Railways API v1 (api.railradar.in).
"""
            state["response"] = reply
            state["provider"] = "railradar_train_tracker"
            return state


    # Case 4: Bus & Urban Transit (STRICT REQUIREMENT: MUST explicitly mention bus/travels keywords)
    bus_keywords = ["bus", "buses", "travels", "redbus", "abhibus", "msrtc", "shivshahi", "shivneri", "konduskar", "sharma", "zingbus", "sleeper coach", "volvo bus", "intercity bus"]
    is_bus_query = any(k in lower for k in bus_keywords)

    if is_bus_query:
        orig_city, dest_city = extract_route_pair(query)
        if not orig_city or not dest_city:
            if "pune" in lower and "mumbai" in lower:
                orig_city, dest_city = "Mumbai", "Pune"
            elif "delhi" in lower and "jaipur" in lower:
                orig_city, dest_city = "Delhi", "Jaipur"
            elif "kolhapur" in lower and "latur" in lower:
                orig_city, dest_city = "Kolhapur", "Latur"
            else:
                orig_city, dest_city = "Mumbai", "Pune"
            
        buses = GTFSAndBusRetriever.search_intercity_buses(orig_city, dest_city)
        
        bus_rows = ""
        for idx, b in enumerate(buses, 1):
            bus_rows += f"**{idx}. {b.get('operator')}** ({b.get('bus_type')})\n"
            bus_rows += f"• **Departure**: {b.get('departure_time')} from **{b.get('origin_point')}**\n"
            bus_rows += f"• **Arrival**: {b.get('arrival_time')} at **{b.get('drop_point')}**\n"
            bus_rows += f"• **Duration**: {b.get('duration')} | **Fare**: **₹{b.get('fare_inr')} INR**\n"
            if b.get('route'):
                bus_rows += f"• **Corridor / Route**: {b.get('route')}\n"
            bus_rows += f"• **Booking**: [{b.get('provider')}]({b.get('booking_link')})\n\n"

        reply = f"""### 🚌 Intercity Travel & Bus Departures ({orig_city} ➔ {dest_city})

Here are verified daily departures across premier state and private transport fleets:

{bus_rows}
#### 💡 Travel Tips:
• **State Road Transport**: Reliable, frequent state-guaranteed services departing from Central Bus Stands (CBS).
• **Private AC Sleepers**: Recommended for overnight travel; equipped with charging ports and blankets. Book via [redBus](https://www.redbus.in) or [AbhiBus](https://www.abhibus.com).
"""
        state["response"] = reply
        state["provider"] = "gtfs_redbus_aggregator"
        return state

    # Case 5: Disruption Evaluation & Statutory Passenger Rights
    if any(k in lower for k in ["delay", "cancel", "refund", "flight", "train", "pnr", "indigo", "air india", "vande bharat", "dgca", "rights", "compensation"]):
        db_disruptions = get_all_external_disruptions()
        candidate_ticket = state.get("structured_ticket") or (db_disruptions[0] if db_disruptions else None)
        
        if candidate_ticket:
            carrier = candidate_ticket.get("carrier", "Carrier")
            service = candidate_ticket.get("service_number", "Service")
            orig = candidate_ticket.get("origin", "Origin")
            dest = candidate_ticket.get("destination", "Destination")
            pnr = candidate_ticket.get("pnr", "N/A")
            pax = candidate_ticket.get("passenger_name", "Passenger")
            delay_m = int(candidate_ticket.get("delay_minutes", 0) or 0)
            is_canc = bool(candidate_ticket.get("is_cancellation", False))
            cost_val = candidate_ticket.get("ticket_cost")
            fare = float(cost_val) if (cost_val is not None and float(cost_val) > 0) else 0.0
            fare_str = f"₹{fare:,.2f} INR" if fare > 0 else "Standard Fare"
            
            rights = evaluate_disruption_rights(carrier, delay_m, is_canc, fare)
            is_rail = "rail" in carrier.lower() or "train" in carrier.lower() or "irctc" in carrier.lower()
            
            if is_rail:
                tdr_eligible = delay_m >= 180 or is_canc
                reply = f"""### 🛡️ Statutory Disruption & IRCTC TDR Evaluation :: {carrier} {service}

I have evaluated your booked travel document from the Voyage Disruption Ledger:

• **Passenger**: **{pax}** (PNR: `{pnr}`)
• **Service**: **{carrier} {service}** ({orig} ➔ {dest})
• **Recorded Delay**: **{"+ " + str(delay_m) + " minutes delay" if delay_m > 0 else "On Schedule / Right Time"}**
• **Ticket Fare**: {fare_str}

---

#### ⚖️ Statutory Passenger Rights & Refund Rules:
• **Governing Framework**: {rights['applicable_law']}
• **TDR Refund Eligibility**: **{"100% Full Fare Refund Eligible (Zero Cancellation Deductions)" if tdr_eligible else "Nominal Schedule (No delay deduction triggered)"}**
• **IRCTC Rule Clause**: Under Indian Railways TDR regulations, if your train is delayed by **more than 3 hours** at your boarding station, you can surrender your ticket via online TDR before train departure for a complete 100% full refund with zero cancellation charges.
• **Duty of Care**: Station amenities, waiting halls, and charting priority are guaranteed under the Indian Railways Citizen Charter.

Feel free to ask for live GPS tracking or assistance in lodging a refund claim!"""
            else:
                reply = f"""### 🛡️ Statutory Disruption & DGCA Evaluation :: {carrier} {service}

I have evaluated your booked travel document from the Voyage Disruption Ledger:

• **Passenger**: **{pax}** (PNR: `{pnr}`)
• **Flight**: **{carrier} {service}** ({orig} ➔ {dest})
• **Operational Status**: **{"+ " + str(delay_m) + " minutes delay" if not is_canc else "Flight Cancelled"}**
• **Ticket Fare**: {fare_str}

---

#### ⚖️ Statutory Passenger Rights & Compensation:
• **Governing Framework**: {rights['applicable_law']}
• **Full Fare Refund**: {"Eligible (100% refund without cancellation deductions)" if rights['refund_eligible'] else "Standard carrier refund policy"}
• **Direct Statutory Compensation**: **₹{rights['statutory_compensation']:,.2f} INR** (Direct compensation under DGCA CAR Section 3)
• **Duty of Care**: Mandatory refreshments/meals at departure terminal during delays exceeding 2 hours.

You can click **"File Claim"** to lodge this statutory refund claim directly into the Voyage Disruption Ledger!"""
            state["response"] = reply
            state["provider"] = "voyage_legal_expert"
            return state
        else:
            reply = """### 🛡️ Statutory Passenger Rights & Delay Compensation Guide

Here are the active statutory protections for travel disruptions:

#### ✈️ Aviation Protections (DGCA CAR Section 3, India):
• **Delays > 2 Hours**: Mandatory complimentary meals and refreshments at the departure terminal.
• **Delays > 6 Hours or Cancellations**: Choice between full 100% cash refund within 7 days OR immediate alternative flight rebooking, plus statutory cash compensation up to ₹5,000–₹10,000.
• **Denied Boarding**: Up to 400% of booked one-way basic fare plus airline fuel charge.

#### 🚆 Indian Railways (IRCTC TDR Regulations):
• **Delays > 3 Hours at Boarding Station**: 100% full refund with zero cancellation fee by filing an online TDR before actual train departure.
• **Train Cancellation by Railways**: 100% automatic full refund directly credited to original bank/card account.

Please upload your ticket (PDF, image, or text) to automatically calculate your exact refund and compensation amount!"""
            state["response"] = reply
            state["provider"] = "voyage_legal_expert"
            return state

    # Case 3: General knowledge / fallback
    state["response"] = f"""Hello! I am your Voyage Disruption & Travel Resilience Assistant.

I can assist you with:
- **Instant Flight & Train Disruption Resolving**: Upload your ticket or tell me your flight delay details, and I will compute connection slack margins and reroute your trip.
- **Statutory Passenger Rights**: Enforcing full fare refunds and cash compensation under DGCA CAR Section 3, EU261, US DOT 2024, and IRCTC TDR rules.
- **Engineering & Code Generation**: Ask me to write full code for travel websites, booking systems, topological algorithms, or React widgets.

How may I assist your journey today?"""
    state["provider"] = "voyage_assistant"
    return state

def run_ai_chat(
    messages: List[Dict[str, str]], 
    user_query: Optional[str] = None,
    groq_api_key: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    active_ticket: Optional[Dict[str, Any]] = None,
    uploaded_tickets: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Executes Voyage AI Agent with domain restrictions and multi-provider failover:
    Gemini -> Groq -> Local Expert Engine
    """
    query = (user_query or (messages[-1]["content"] if messages else "")).strip()

    # Domain restriction check: block off-topic code generation, math problem solving, and general non-travel tasks
    is_off_topic, category = is_off_topic_query(query)
    if is_off_topic:
        return {
            "reply": get_domain_restriction_response(category),
            "provider": "Voyage Domain Guard",
            "model": "Domain-Restricted",
            "success": True
        }

    live_context_parts = []
    extracted_train_card = None
    buses_result = None

    # Ingest real passenger disruption records and refund claims from SQLite database
    db_disruptions = get_all_external_disruptions()
    db_claims = get_all_refund_claims()

    all_tickets = []
    if uploaded_tickets:
        all_tickets.extend(uploaded_tickets)
    if db_disruptions:
        all_tickets.extend(db_disruptions)

    # Deduplicate tickets by id or (pnr + service_number)
    dedup_tickets = []
    seen_keys = set()
    for t in all_tickets:
        k = str(t.get("id")) if t.get("id") else f"{t.get('pnr')}_{t.get('service_number')}"
        if k not in seen_keys:
            seen_keys.add(k)
            dedup_tickets.append(t)
    all_tickets = dedup_tickets

    # Default active ticket to latest record if not provided
    if not active_ticket and all_tickets:
        active_ticket = all_tickets[0]

    # Find matching ticket if user query mentions a specific train number, PNR, or route
    train_match = re.search(r'\b([012]\d{4})\b', query)
    matched_ticket = None
    for t in all_tickets:
        svc = str(t.get("service_number", ""))
        pnr_val = str(t.get("pnr", ""))
        m_num = re.search(r'\b([012]\d{4})\b', svc)
        num_in_ticket = m_num.group(1) if m_num else ""
        if train_match and num_in_ticket == train_match.group(1):
            matched_ticket = t
            break
        elif pnr_val and pnr_val.lower() in query.lower():
            matched_ticket = t
            break

    if matched_ticket:
        active_ticket = matched_ticket

    # Inject real database passenger ledger into AI context
    if all_tickets:
        legs_info = []
        for idx, t in enumerate(all_tickets, 1):
            is_past_str = " (COMPLETED RUN)" if t.get("is_past_journey") else ""
            del_m = int(t.get('delay_minutes', 0) or 0)
            delay_str = f"+{del_m}m delay" if del_m > 0 else "Running Right Time (On-Time)"
            pname = t.get('passenger_name') or 'Passenger'
            cost_val = t.get('ticket_cost')
            fare_val = f"₹{float(cost_val):,.2f} {t.get('currency', 'INR')}" if (cost_val is not None and float(cost_val) > 0) else "Standard Fare"
            legs_info.append(
                f"- Leg {idx}: PNR: `{t.get('pnr')}` | Passenger: {pname} | Carrier: {t.get('carrier')} {t.get('service_number')} | Corridor: {t.get('origin')} ➔ {t.get('destination')} | Travel Date: {t.get('travel_date', 'Recent')}{is_past_str} | Status: {t.get('journey_status', 'ON_TIME')} ({delay_str}) | Fare: {fare_val} | Disruption: {t.get('disruption_reason', 'None')}"
            )
        live_context_parts.append(
            "INGESTED PASSENGER BOOKING & DISRUPTION LEDGER (REAL RECORDS FROM SQLITE DATABASE):\n"
            + "\n".join(legs_info) +
            "\n\nINSTRUCTION: Always refer to these authentic passenger tickets. Do not make up or invent mock carriers, flights, trains, fares, or passenger names."
        )

    # Inject filed refund claims ledger if available
    if db_claims:
        claims_info = []
        for c in db_claims:
            c_amt = float(c.get('claimed_amount', 0) or 0)
            claims_info.append(
                f"- Claim ID: {c.get('claim_id')} | PNR: `{c.get('pnr')}` | Passenger: {c.get('passenger_name')} | Carrier: {c.get('airline')} | Claimed: ₹{c_amt:,.2f} {c.get('currency', 'INR')} | Status: {c.get('claim_status')} | Policy: {c.get('applicable_policy')} | Filed: {c.get('filing_timestamp')}"
            )
        live_context_parts.append(
            "FILED STATUTORY REFUND CLAIMS LEDGER (REAL RECORDS FROM SQLITE DATABASE):\n"
            + "\n".join(claims_info) +
            "\n\nINSTRUCTION: When asked about claims, refunds, or dispute filings, report these actual filed claims from the database with their claim IDs, amounts, and filing status."
        )

    # 1. Detect train query (5-digit Indian Railways train number) or reference to active ticket train
    act_service = str(active_ticket.get("service_number", "")) if active_ticket else ""
    act_train_match = re.search(r'\b([012]\d{4})\b', act_service)
    target_train_num = None
    if train_match:
        target_train_num = train_match.group(1)
    elif act_train_match and any(w in query.lower() for w in ["train", "status", "track", "delay", "running", "location", "where", "ticket", "trip", "journey", "my", "schedule", "info", "pnr", "summary", "give"]):
        target_train_num = act_train_match.group(1)

    if target_train_num:
        try:
            from .travel_retrieval import RailRadarTracker
            t_data = RailRadarTracker.get_live_train_status(target_train_num)
            if t_data and t_data.get("train_name"):
                delay_val = t_data.get('delay_minutes', 0)
                delay_str = f"+{delay_val} mins delay" if delay_val > 0 else "Running Right Time (On-Time)"

                # Check if active_ticket is for this train
                is_ticket_for_train = bool(active_ticket and (
                    (target_train_num and target_train_num in str(active_ticket.get("service_number", ""))) or
                    "train" in str(active_ticket.get("carrier", "")).lower() or
                    "rail" in str(active_ticket.get("carrier", "")).lower()
                ))

                ticket_origin = active_ticket.get("origin") if (active_ticket and is_ticket_for_train) else None
                ticket_dest = active_ticket.get("destination") if (active_ticket and is_ticket_for_train) else None

                orig_disp = ticket_origin or t_data.get("origin", "Origin")
                dest_disp = ticket_dest or t_data.get("destination", "Destination")

                route_segment_info = f"- Passenger Booked Ticket Segment: {orig_disp} ➔ {dest_disp}\n" if (ticket_origin and ticket_dest) else ""
                route_segment_info += f"- Full Train Operational Run: {t_data.get('origin', '')} ({t_data.get('origin_code', '')}) ➔ {t_data.get('destination', '')} ({t_data.get('destination_code', '')})"

                dest_instruction = ""
                if ticket_dest and ticket_dest != t_data.get("destination"):
                    dest_instruction = (
                        f"\n\nCRITICAL PASSENGER ROUTE INSTRUCTION:\n"
                        f"The passenger's booked ticket destination is strictly {dest_disp}, boarding at {orig_disp}.\n"
                        f"Although train #{t_data['train_number']}'s full terminus is {t_data.get('destination')}, the passenger DEBARKS at {dest_disp}.\n"
                        f"Always address the passenger's journey as traveling to {dest_disp}. Do NOT tell them they are traveling to {t_data.get('destination')}."
                    )

                live_context_parts.append(
                    f"REAL-TIME RAILRADAR TELEMETRY FOR TRAIN #{t_data['train_number']} ({t_data['train_name']}):\n"
                    f"- Service: #{t_data['train_number']} {t_data['train_name']}\n"
                    f"{route_segment_info}\n"
                    f"- Status: {t_data.get('status', 'running')} (Live GPS Tracking: {t_data.get('is_live', True)})\n"
                    f"- Current Location: Approaching/at {t_data.get('current_location', 'In transit')}\n"
                    f"- Next Station / Halt: {t_data.get('upcoming_station', 'En route')}\n"
                    f"- Previous Station: {t_data.get('prev_station', 'N/A')}\n"
                    f"- Current Delay: {delay_str}\n"
                    f"- Distance Remaining on full service: {t_data.get('distance_remaining_km', 0)} km\n"
                    f"- Average Speed: {t_data.get('avg_speed_kmh', 0)} km/h\n"
                    f"- IRCTC TDR Refund: {'Eligible (100% refund, delay >= 3 hrs)' if t_data.get('tdr_refund_eligible') else 'Nominal (delay < 3 hrs)'}\n"
                    f"INSTRUCTION: When answering, provide these accurate real-time live telemetry details for this train.{dest_instruction}"
                )
                
                ticket_pnr = active_ticket.get("pnr") if (active_ticket and is_ticket_for_train) else None
                ticket_cost = active_ticket.get("ticket_cost") if (active_ticket and is_ticket_for_train) else None
                pax_name = active_ticket.get("passenger_name", "Passenger") if (active_ticket and is_ticket_for_train) else "Passenger"
                
                extracted_train_card = {
                    "carrier": "Indian Railways",
                    "service_number": f"#{t_data['train_number']} {t_data['train_name']}",
                    "origin": orig_disp,
                    "destination": dest_disp,
                    "delay_minutes": delay_val,
                    "is_cancellation": False,
                    "is_past_journey": active_ticket.get("is_past_journey", False) if (active_ticket and is_ticket_for_train) else False,
                    "disruption_reason": f"Live location: {t_data.get('current_location', 'In transit')} • {delay_str}",
                    "pnr": ticket_pnr or f"LIVE-ENQ-{t_data['train_number']}",
                    "ticket_cost": ticket_cost,
                    "currency": active_ticket.get("currency", "INR") if active_ticket else "INR",
                    "passenger_name": pax_name,
                    "current_location": t_data.get("current_location"),
                    "upcoming_station": t_data.get("upcoming_station"),
                    "status": t_data.get("status"),
                    "train_terminus_origin": t_data.get("origin"),
                    "train_terminus_destination": t_data.get("destination"),
                    "source": "RailRadar Live API v1"
                }
        except Exception as e:
            pass

    # 1b. Train Route Corridor Query (e.g. "train from Mumbai to Delhi", "trains between Delhi and Jaipur")
    train_keywords = ["train", "trains", "rail", "railway", "irctc", "railradar", "vande bharat", "rajdhani", "shatabdi", "duronto", "tejas", "express"]
    is_train_route = any(w in query.lower() for w in train_keywords) and not train_match
    if is_train_route:
        orig_t, dest_t = extract_route_pair(query)
        if not orig_t or not dest_t:
            if "mumbai" in query.lower() and "delhi" in query.lower():
                orig_t, dest_t = "Mumbai", "Delhi"
            elif "delhi" in query.lower() and "jaipur" in query.lower():
                orig_t, dest_t = "Delhi", "Jaipur"
            elif "mumbai" in query.lower() and "pune" in query.lower():
                orig_t, dest_t = "Mumbai", "Pune"
        if orig_t and dest_t and orig_t.lower() != dest_t.lower():
            try:
                from .travel_retrieval import RailRadarTracker
                live_trains = RailRadarTracker.search_route_trains(orig_t, dest_t)
                if live_trains:
                    tr_rows = []
                    for tr in live_trains:
                        del_val = tr.get("delay_minutes", 0)
                        del_str = f"+{del_val} mins delay" if del_val > 0 else "Running Right Time (On-Time)"
                        tr_rows.append(
                            f"| **#{tr['train_number']}** | {tr['train_name']} | **{tr['status'].upper()}** | {tr.get('current_location', 'In transit')} | {tr.get('upcoming_station', 'En route')} | {del_str} | {'100% Refund Eligible' if tr.get('tdr_refund_eligible') else 'Normal'} |"
                        )
                    live_context_parts.append(
                        f"REAL-TIME RAILRADAR TELEMETRY FOR TRAINS ({orig_t} ➔ {dest_t}):\n"
                        "| Train # | Service Name | Status | Current Location | Next Station | Delay | IRCTC TDR |\n"
                        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
                        + "\n".join(tr_rows) +
                        "\n\nINSTRUCTION: Present these real-time live trains from RailRadar API v1 in a clear Markdown table with their exact live GPS locations and delays. State IRCTC TDR refund eligibility (if delay >= 3 hrs at boarding, 100% full refund with zero cancellation penalty)."
                    )
            except Exception:
                pass

    # 2. Detect specific flight query (e.g. AI 882, 6E 521, BA 712)
    flight_match = re.search(r'\b([A-Za-z]{2}\s?\d{3,4})\b', query)
    if flight_match and any(w in query.lower() for w in ["flight", "fight", "status", "track", "radar", "airline", "delay"]):
        flight_code = flight_match.group(1).upper()
        if flight_code not in ["TO", "ME", "IN", "IS", "ON", "AT"]:
            try:
                from .travel_retrieval import AviationStackTracker
                tracker = AviationStackTracker()
                f_data = tracker.get_flight_status(flight_code)
                if f_data and f_data.get("airline"):
                    delay_m = f_data.get("delay_minutes", 0)
                    delay_str = f"+{delay_m} mins delay" if delay_m > 0 else "On Schedule"
                    live_context_parts.append(
                        f"REAL-TIME AVIATIONSTACK TELEMETRY FOR FLIGHT {f_data.get('flight_iata', flight_code)}:\n"
                        f"- Airline: {f_data.get('airline')}\n"
                        f"- Route: {f_data.get('departure_airport', '')} ({f_data.get('departure_iata', '')}) ➔ {f_data.get('arrival_airport', '')} ({f_data.get('arrival_iata', '')})\n"
                        f"- Status: {f_data.get('status', 'scheduled').upper()} ({delay_str})\n"
                        f"- Departure Gate / Terminal: {f_data.get('departure_terminal', 'TBD')} / Gate {f_data.get('departure_gate', 'TBD')}\n"
                        f"- Scheduled Departure: {f_data.get('scheduled_departure', 'N/A')}\n"
                        f"- Estimated Arrival: {f_data.get('estimated_arrival', 'N/A')}\n"
                        f"- Aircraft: {f_data.get('aircraft', 'Commercial Jet')}\n"
                        "INSTRUCTION: When answering, provide these accurate real-time live flight radar details."
                    )
            except Exception:
                pass

    # 2b. Multi-turn Flight Corridor & Schedule Search (e.g. "search flights from Mumbai to Delhi", "27 sep", "look schedule for morning")
    full_context_text = " ".join([m.get("content", "") for m in messages]) + " " + query
    full_lower = full_context_text.lower()
    flight_keywords = ["flight", "flights", "fight", "flite", "fly", "flying", "plane", "planes", "airline", "airlines", "airways", "airfare"]
    is_flight_intent = any(w in full_lower for w in flight_keywords)

    if is_flight_intent:
        orig_f, dest_f = "", ""
        m_rt = re.search(r'(?:from|between)\s+([a-zA-Z\s]+?)\s+(?:to|and)\s+([a-zA-Z\s]+)', full_context_text, re.IGNORECASE)
        if m_rt:
            o_clean = re.sub(r'^(?:can\s+you\s+)?(?:please\s+)?(?:give|show|tell|find|search|check|get|me|info|information|details|about|tickets?|schedule|status|flights?|fights?|options?|for|the|cheap|cheapest|any)\s+', '', m_rt.group(1).strip(), flags=re.I).strip()
            d_clean = re.sub(r'\s+(?:flights?|fights?|options?|details?|tickets?|today|tomorrow|now|please|morning|evening|night|afternoon|\d{1,2}\s+[a-zA-Z]+)$', '', m_rt.group(2).strip(), flags=re.I).strip()
            orig_f, dest_f = o_clean, d_clean

        if not orig_f or not dest_f:
            if "mumbai" in full_lower and "delhi" in full_lower:
                orig_f, dest_f = "Mumbai", "Delhi"
            elif "bangalore" in full_lower and "delhi" in full_lower:
                orig_f, dest_f = "Bangalore", "Delhi"
            elif "mumbai" in full_lower and "bangalore" in full_lower:
                orig_f, dest_f = "Mumbai", "Bangalore"
            elif "mumbai" in full_lower and "goa" in full_lower:
                orig_f, dest_f = "Mumbai", "Goa"
            elif "delhi" in full_lower and "jaipur" in full_lower:
                orig_f, dest_f = "Delhi", "Jaipur"

        if orig_f and dest_f and orig_f.lower() != dest_f.lower():
            o_loc = lookup_location(orig_f)
            d_loc = lookup_location(dest_f)
            dep_code = o_loc["code"] if o_loc else orig_f[:3].upper()
            arr_code = d_loc["code"] if d_loc else dest_f[:3].upper()

            # Detect date in conversation
            date_str = None
            d_match = re.search(r'\b(\d{1,2})\s*(?:th|st|nd|rd)?\s*(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b', full_context_text, re.IGNORECASE)
            if d_match:
                date_str = f"{d_match.group(2).capitalize()} {d_match.group(1)}"
            elif "tomorrow" in full_lower:
                date_str = "Tomorrow"
            elif "today" in full_lower:
                date_str = "Today"

            # Detect time window
            time_win = None
            if any(w in query.lower() for w in ["morning", "early", "am", "dawn"]):
                time_win = "morning"
            elif any(w in query.lower() for w in ["afternoon", "noon", "midday", "lunch"]):
                time_win = "afternoon"
            elif any(w in query.lower() for w in ["evening", "dusk"]):
                time_win = "evening"
            elif any(w in query.lower() for w in ["night", "late", "pm", "red eye", "overnight"]):
                time_win = "night"

            try:
                from .travel_retrieval import AviationStackTracker
                tracker = AviationStackTracker()
                route_flights = tracker.search_route_flights(dep_iata=dep_code, arr_iata=arr_code, flight_date=date_str, time_window=time_win)
                if route_flights:
                    fl_rows = []
                    for rf in route_flights:
                        fl_rows.append(
                            f"| {rf['departure_time']} | **{rf['flight_iata']}** | {rf['airline']} | {rf['departure_iata']} ({rf['departure_terminal']}) ➔ {rf['arrival_iata']} ({rf['arrival_terminal']}) | {rf['duration']} | ₹{rf['estimated_fare_inr']:,} INR | {rf['status'].upper()} |"
                        )
                    
                    context_header = f"VERIFIED LIVE FLIGHT SCHEDULE ({orig_f} [{dep_code}] ➔ {dest_f} [{arr_code}])"
                    if date_str:
                        context_header += f" FOR {date_str.upper()}"
                    if time_win:
                        context_header += f" ({time_win.upper()} WINDOW)"

                    live_context_parts.append(
                        f"{context_header}:\n"
                        "| Departure | Flight | Airline | Route / Terminals | Duration | Est. Fare | Status |\n"
                        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
                        + "\n".join(fl_rows) +
                        "\n\nINSTRUCTION: Present these concrete real flights immediately to the traveler in a clean, structured Markdown table with exact times in IST, flight codes, airlines, terminals, duration, and estimated fares in INR. Only list actual operating carriers (IndiGo, Air India, Akasa Air, Air India Express, SpiceJet; note that Vistara merged into Air India). Highlight operational resilience (early morning departures have lowest ATC congestion delay risk). Conclude with DGCA CAR Section 3 statutory passenger rights (>2h delay = complimentary meals, >6h delay/cancellation = 100% full refund). DO NOT ask open questions without presenting this structured schedule table first."
                    )
            except Exception:
                pass

    # 3. Detect bus / travels query between two cities (STRICT: only if bus keywords present)
    bus_keywords = ["bus", "buses", "travels", "redbus", "abhibus", "msrtc", "shivshahi", "shivneri", "konduskar", "sharma", "zingbus", "sleeper", "volvo bus", "intercity bus"]
    has_bus_intent = any(w in query.lower() for w in bus_keywords)
    bus_query_pattern = re.search(r'(?:travels?|buses?|bus|ride|taxi|cab|road)\s+(?:from|between)\s+([a-zA-Z\s]+?)\s+(?:to|and)\s+([a-zA-Z\s]+)', query, re.IGNORECASE)
    if not bus_query_pattern and has_bus_intent:
        bus_query_pattern = re.search(r'(?:from\s+)?([a-zA-Z\s]+?)\s+to\s+([a-zA-Z\s]+?)(?:\s+(?:travels?|buses?|bus|route))?$', query, re.IGNORECASE)
    
    if bus_query_pattern and has_bus_intent:
        orig_candidate = bus_query_pattern.group(1).strip()
        dest_candidate = bus_query_pattern.group(2).strip()
        orig_clean = re.sub(r'^(search|give|show|find|list|for|the)\s+', '', orig_candidate, flags=re.I).strip().title()
        dest_clean = re.sub(r'\s+(travels?|buses?|bus|options|details)$', '', dest_candidate, flags=re.I).strip().title()
        if len(orig_clean) >= 3 and len(dest_clean) >= 3 and orig_clean.lower() != dest_clean.lower():
            try:
                from .travel_retrieval import GTFSAndBusRetriever
                buses = GTFSAndBusRetriever.search_intercity_buses(orig_clean, dest_clean)
                if buses:
                    buses_result = buses
                    bus_lines = []
                    for idx, b in enumerate(buses, 1):
                        bus_lines.append(
                            f"{idx}. {b.get('operator')} ({b.get('bus_type')}):\n"
                            f"   • Departs: {b.get('departure_time')} from {b.get('origin_point')}\n"
                            f"   • Arrives: {b.get('arrival_time')} at {b.get('drop_point')}\n"
                            f"   • Duration: {b.get('duration')} | Fare: ₹{b.get('fare_inr')} INR\n"
                            f"   • Route / Highlights: {b.get('route', ', '.join(b.get('amenities', [])))}\n"
                            f"   • Booking: {b.get('provider')} ({b.get('booking_link')})"
                        )
                    live_context_parts.append(
                        f"VERIFIED INTERCITY BUS & TRAVEL OPERATOR SCHEDULE ({orig_clean} ➔ {dest_clean}):\n"
                        + "\n".join(bus_lines) +
                        f"\n\nINSTRUCTION: The user is specifically asking for travel/bus options between {orig_clean} and {dest_clean}. "
                        "1. Give a comprehensive, structured breakdown featuring these departures with specific operators, departure times, boarding stands, drop points, exact fares in INR, and booking guidance. "
                        "2. IMPORTANT: At the end of your response, explicitly ask the traveler what time of day or specific hour they prefer to depart (e.g. 🌅 Morning 06:00–12:00, ☀️ Afternoon 12:00–18:00, or 🌙 Overnight Sleeper after 20:00), so you can narrow down or suggest the best schedule for them."
                    )
            except Exception as e:
                pass

    # 4. Detect web URL to scrape live information
    url_match = re.search(r'https?://[^\s<>"]+', query)
    if url_match:
        target_url = url_match.group(0).rstrip('.,;:)')
        try:
            from .scraper_tool import AgentWebScraper
            scraped = AgentWebScraper.scrape_url(target_url, max_text_length=3000)
            if scraped.get("status") == "SUCCESS":
                live_context_parts.append(
                    f"LIVE WEBPAGE CONTENT EXTRACTED FROM {target_url}:\n"
                    f"Title: {scraped.get('title', 'N/A')}\n"
                    f"Description: {scraped.get('description', 'N/A')}\n"
                    f"Extracted Content:\n{scraped.get('text_preview', '')}\n\n"
                    "INSTRUCTION: Use this live scraped web content to answer the user's question accurately."
                )
        except Exception:
            pass

    live_context_str = "\n\n".join(live_context_parts) if live_context_parts else None

    # Determine structured ticket for agent state and UI response
    if active_ticket and extracted_train_card:
        merged_ticket = dict(active_ticket)
        merged_ticket.update({
            "current_location": extracted_train_card.get("current_location"),
            "upcoming_station": extracted_train_card.get("upcoming_station"),
            "delay_minutes": extracted_train_card.get("delay_minutes", active_ticket.get("delay_minutes", 0)),
            "disruption_reason": extracted_train_card.get("disruption_reason"),
            "status": extracted_train_card.get("status"),
            "source": extracted_train_card.get("source"),
            # ALWAYS PRESERVE passenger ticket origin and destination!
            "origin": active_ticket.get("origin") or extracted_train_card.get("origin"),
            "destination": active_ticket.get("destination") or extracted_train_card.get("destination"),
        })
        final_ticket = merged_ticket
    else:
        final_ticket = extracted_train_card or active_ticket

    state: AgentState = {
        "messages": messages,
        "user_query": query,
        "response": None,
        "provider": None,
        "structured_ticket": final_ticket,
        "live_context": live_context_str,
        "error": None
    }

    # 1. Attempt Google Gemini with multi-key failover
    gem_keys = get_gemini_keys(gemini_api_key)
    if gem_keys and genai is not None:
        for gk in gem_keys:
            try:
                state = call_gemini(state, gk)
                if state.get("response"):
                    res = {
                        "reply": state["response"],
                        "provider": "Voyage AI Engine (Gemini)",
                        "success": True,
                        "all_tickets": all_tickets
                    }
                    if final_ticket and (extracted_train_card or any(k in query.lower() for k in ["trip", "ticket", "train", "flight", "status", "detail", "pnr", "my", "delay", "summary"])):
                        res["structured_ticket"] = final_ticket
                    if buses_result:
                        res["buses"] = buses_result
                    return res
            except Exception:
                continue

    # 2. Attempt Groq with multi-key failover
    gr_keys = get_groq_keys(groq_api_key)
    if gr_keys and Groq is not None:
        for qk in gr_keys:
            try:
                state = call_groq(state, qk)
                if state.get("response"):
                    res = {
                        "reply": state["response"],
                        "provider": "Voyage AI Engine (Groq)",
                        "success": True,
                        "all_tickets": all_tickets
                    }
                    if final_ticket and (extracted_train_card or any(k in query.lower() for k in ["trip", "ticket", "train", "flight", "status", "detail", "pnr", "my", "delay", "summary"])):
                        res["structured_ticket"] = final_ticket
                    if buses_result:
                        res["buses"] = buses_result
                    return res
            except Exception:
                continue

    # 3. Fallback to Local Voyage Expert Engine
    state = call_expert_engine(state)
    res = {
        "reply": state["response"],
        "provider": state.get("provider") or "Voyage AI Engine",
        "success": True,
        "all_tickets": all_tickets
    }
    if final_ticket and (extracted_train_card or any(k in query.lower() for k in ["trip", "ticket", "train", "flight", "status", "detail", "pnr", "my", "delay", "summary"])):
        res["structured_ticket"] = final_ticket
    if buses_result:
        res["buses"] = buses_result
    return res

KNOWN_LOCATIONS = {
    # Major Indian Aviation & Rail Hubs (including Maharashtra & Central Railway corridors)
    "ami": {"name": "Amravati (AMI)", "city": "Amravati", "code": "AMI", "lat": 20.9374, "lng": 77.7796, "aliases": ["amravati", "ami"]},
    "bsl": {"name": "Bhusaval Jn. (BSL)", "city": "Bhusaval", "code": "BSL", "lat": 21.0455, "lng": 75.8011, "aliases": ["bhusaval", "bhusawal", "bsl", "bhusaval jn", "bhusawal jn"]},
    "bd": {"name": "Badnera Jn. (BD)", "city": "Badnera", "code": "BD", "lat": 20.8569, "lng": 77.7289, "aliases": ["badnera", "bd", "badnera jn"]},
    "ak": {"name": "Akola Jn. (AK)", "city": "Akola", "code": "AK", "lat": 20.7059, "lng": 77.0219, "aliases": ["akola", "ak", "akola jn"]},
    "wr": {"name": "Wardha Jn. (WR)", "city": "Wardha", "code": "WR", "lat": 20.7453, "lng": 78.6022, "aliases": ["wardha", "wr", "wardha jn"]},
    "ngp": {"name": "Nagpur Jn. (NGP)", "city": "Nagpur", "code": "NGP", "lat": 21.1524, "lng": 79.0888, "aliases": ["nagpur", "ngp", "nag", "nagpur jn"]},
    "jl": {"name": "Jalgaon Jn. (JL)", "city": "Jalgaon", "code": "JL", "lat": 21.0077, "lng": 75.5626, "aliases": ["jalgaon", "jl", "jalgaon jn"]},
    "mmr": {"name": "Manmad Jn. (MMR)", "city": "Manmad", "code": "MMR", "lat": 20.2520, "lng": 74.4410, "aliases": ["manmad", "mmr", "manmad jn"]},
    "nk": {"name": "Nashik Road (NK)", "city": "Nashik", "code": "NK", "lat": 19.9572, "lng": 73.8340, "aliases": ["nashik", "nasik", "nk", "nashik road"]},
    "kyn": {"name": "Kalyan Jn. (KYN)", "city": "Kalyan", "code": "KYN", "lat": 19.2437, "lng": 73.1355, "aliases": ["kalyan", "kyn", "kalyan jn"]},
    "tna": {"name": "Thane (TNA)", "city": "Thane", "code": "TNA", "lat": 19.1860, "lng": 72.9759, "aliases": ["thane", "tna"]},
    "dr": {"name": "Dadar (DR)", "city": "Mumbai", "code": "DR", "lat": 19.0178, "lng": 72.8478, "aliases": ["dadar", "dr"]},
    "csmt": {"name": "Mumbai CSMT (CSMT)", "city": "Mumbai", "code": "CSMT", "lat": 18.9401, "lng": 72.8351, "aliases": ["csmt", "cst", "mumbai csmt", "chhatrapati shivaji maharaj terminus"]},
    "del": {"name": "Delhi (DEL)", "city": "Delhi", "code": "DEL", "lat": 28.5562, "lng": 77.1000, "aliases": ["delhi", "new delhi", "ndls", "igi", "del"]},
    "bom": {"name": "Mumbai (BOM)", "city": "Mumbai", "code": "BOM", "lat": 19.0896, "lng": 72.8656, "aliases": ["mumbai", "bombay", "bom"]},
    "blr": {"name": "Bangalore (BLR)", "city": "Bangalore", "code": "BLR", "lat": 12.9716, "lng": 77.5946, "aliases": ["bangalore", "bengaluru", "sbc", "blr", "kempegowda", "ypr"]},
    "hyd": {"name": "Hyderabad (HYD)", "city": "Hyderabad", "code": "HYD", "lat": 17.2403, "lng": 78.4294, "aliases": ["hyderabad", "secunderabad", "hyd", "rgia", "sc", "kcg"]},
    "jai": {"name": "Jaipur (JAI)", "city": "Jaipur", "code": "JAI", "lat": 26.9124, "lng": 75.7873, "aliases": ["jaipur", "jp", "jai", "sanganer"]},
    "maa": {"name": "Chennai (MAA)", "city": "Chennai", "code": "MAA", "lat": 13.0827, "lng": 80.2707, "aliases": ["chennai", "madras", "maa", "mas", "ms"]},
    "ccu": {"name": "Kolkata (CCU)", "city": "Kolkata", "code": "CCU", "lat": 22.5726, "lng": 88.3639, "aliases": ["kolkata", "calcutta", "ccu", "howrah", "hwh"]},
    "amd": {"name": "Ahmedabad (AMD)", "city": "Ahmedabad", "code": "AMD", "lat": 23.0734, "lng": 72.6347, "aliases": ["ahmedabad", "amd", "adi"]},
    "pnq": {"name": "Pune (PNQ)", "city": "Pune", "code": "PNQ", "lat": 18.5822, "lng": 73.9197, "aliases": ["pune", "poona", "pnq", "pune jn"]},
    "goi": {"name": "Goa (GOI)", "city": "Goa", "code": "GOI", "lat": 15.3800, "lng": 73.8318, "aliases": ["goa", "dabolim", "goi", "mopa", "gox", "madgaon", "mao"]},
    "cok": {"name": "Kochi (COK)", "city": "Kochi", "code": "COK", "lat": 10.1518, "lng": 76.3930, "aliases": ["kochi", "cochin", "cok", "ers"]},
    "lko": {"name": "Lucknow (LKO)", "city": "Lucknow", "code": "LKO", "lat": 26.7606, "lng": 80.8893, "aliases": ["lucknow", "lko"]},
    "ixc": {"name": "Chandigarh (IXC)", "city": "Chandigarh", "code": "IXC", "lat": 30.6735, "lng": 76.7885, "aliases": ["chandigarh", "ixc", "cdg"]},
    "vns": {"name": "Varanasi (VNS)", "city": "Varanasi", "code": "VNS", "lat": 25.4524, "lng": 82.8590, "aliases": ["varanasi", "banaras", "vns", "bsb"]},
    "pat": {"name": "Patna (PAT)", "city": "Patna", "code": "PAT", "lat": 25.5913, "lng": 85.0880, "aliases": ["patna", "pat", "pnbe"]},
    "atq": {"name": "Amritsar (ATQ)", "city": "Amritsar", "code": "ATQ", "lat": 31.7096, "lng": 74.7973, "aliases": ["amritsar", "atq", "asr"]},
    "bbi": {"name": "Bhubaneswar (BBI)", "city": "Bhubaneswar", "code": "BBI", "lat": 20.2444, "lng": 85.8178, "aliases": ["bhubaneswar", "bbi", "bbs"]},
    "gau": {"name": "Guwahati (GAU)", "city": "Guwahati", "code": "GAU", "lat": 26.1061, "lng": 91.5859, "aliases": ["guwahati", "gau", "ghy"]},
    "idr": {"name": "Indore (IDR)", "city": "Indore", "code": "IDR", "lat": 22.7217, "lng": 75.8011, "aliases": ["indore", "idr", "indb"]},
    "cjb": {"name": "Coimbatore (CJB)", "city": "Coimbatore", "code": "CJB", "lat": 11.0299, "lng": 77.0434, "aliases": ["coimbatore", "cjb", "cbe"]},
    "ixe": {"name": "Mangalore (IXE)", "city": "Mangalore", "code": "IXE", "lat": 12.9613, "lng": 74.8901, "aliases": ["mangalore", "mangaluru", "ixe", "maq"]},
    "trv": {"name": "Trivandrum (TRV)", "city": "Trivandrum", "code": "TRV", "lat": 8.4821, "lng": 76.9200, "aliases": ["trivandrum", "thiruvananthapuram", "trv", "tvc"]},
    "vtz": {"name": "Visakhapatnam (VTZ)", "city": "Visakhapatnam", "code": "VTZ", "lat": 17.7215, "lng": 83.2245, "aliases": ["visakhapatnam", "vizag", "vtz", "vskp"]},
    "sxr": {"name": "Srinagar (SXR)", "city": "Srinagar", "code": "SXR", "lat": 33.9871, "lng": 74.7741, "aliases": ["srinagar", "sxr"]},
    "bza": {"name": "Vijayawada (BZA)", "city": "Vijayawada", "code": "BZA", "lat": 16.5304, "lng": 80.7968, "aliases": ["vijayawada", "bza"]},
    "bdq": {"name": "Vadodara (BDQ)", "city": "Vadodara", "code": "BDQ", "lat": 22.3362, "lng": 73.2263, "aliases": ["vadodara", "baroda", "bdq", "brc"]},
    "udr": {"name": "Udaipur (UDR)", "city": "Udaipur", "code": "UDR", "lat": 24.6177, "lng": 73.8961, "aliases": ["udaipur", "udr", "udz"]},
    "ixr": {"name": "Ranchi (IXR)", "city": "Ranchi", "code": "IXR", "lat": 23.3143, "lng": 85.3217, "aliases": ["ranchi", "ixr", "rnc"]},
    "bho": {"name": "Bhopal (BHO)", "city": "Bhopal", "code": "BHO", "lat": 23.2875, "lng": 77.3374, "aliases": ["bhopal", "bho", "bpl"]},
    "gwl": {"name": "Gwalior (GWL)", "city": "Gwalior", "code": "GWL", "lat": 26.2933, "lng": 78.2278, "aliases": ["gwalior", "gwl"]},
    "agr": {"name": "Agra (AGR)", "city": "Agra", "code": "AGR", "lat": 27.1558, "lng": 77.9609, "aliases": ["agra", "agr", "agc"]},
    "r": {"name": "Raipur Jn. (R)", "city": "Raipur", "code": "R", "lat": 21.2514, "lng": 81.6296, "aliases": ["raipur", "r", "raipur jn"]},
    "durg": {"name": "Durg Jn. (DURG)", "city": "Durg", "code": "DURG", "lat": 21.1904, "lng": 81.2849, "aliases": ["durg", "durg jn"]},
    "bsp": {"name": "Bilaspur Jn. (BSP)", "city": "Bilaspur", "code": "BSP", "lat": 22.0797, "lng": 82.1409, "aliases": ["bilaspur", "bsp", "bilaspur jn"]},
    "et": {"name": "Itarsi Jn. (ET)", "city": "Itarsi", "code": "ET", "lat": 21.9213, "lng": 77.7554, "aliases": ["itarsi", "et", "itarsi jn"]},
    "jbp": {"name": "Jabalpur (JBP)", "city": "Jabalpur", "code": "JBP", "lat": 23.1686, "lng": 79.9547, "aliases": ["jabalpur", "jbp"]},
    "st": {"name": "Surat (ST)", "city": "Surat", "code": "ST", "lat": 21.2049, "lng": 72.8407, "aliases": ["surat", "st"]},
    "awb": {"name": "Chhatrapati Sambhaji Nagar (AWB)", "city": "Aurangabad", "code": "AWB", "lat": 19.8636, "lng": 75.3528, "aliases": ["aurangabad", "sambhaji nagar", "chhatrapati sambhaji nagar", "awb"]},
    "ned": {"name": "Nanded (NED)", "city": "Nanded", "code": "NED", "lat": 19.1627, "lng": 77.3168, "aliases": ["nanded", "ned"]},
    "kop": {"name": "Kolhapur (KOP)", "city": "Kolhapur", "code": "KOP", "lat": 16.7050, "lng": 74.2433, "aliases": ["kolhapur", "kop"]},
    "sur": {"name": "Solapur (SUR)", "city": "Solapur", "code": "SUR", "lat": 17.6599, "lng": 75.9064, "aliases": ["solapur", "sur"]},
    # Mumbai Suburban & Commuter Rail Stations
    "pnvl": {"name": "Panvel (PNVL)", "city": "Panvel", "code": "PNVL", "lat": 18.9943, "lng": 73.1104, "aliases": ["panvel", "pnvl", "new panvel", "panvel jn"]},
    "vsl": {"name": "Vasai Road (BSR)", "city": "Vasai", "code": "BSR", "lat": 19.3636, "lng": 72.8296, "aliases": ["vasai", "vasai road", "bsr", "bassein road"]},
    "vr": {"name": "Virar (VR)", "city": "Virar", "code": "VR", "lat": 19.4613, "lng": 72.8056, "aliases": ["virar", "vr"]},
    "diva": {"name": "Diva Jn. (DIVA)", "city": "Diva", "code": "DIVA", "lat": 19.2167, "lng": 73.0667, "aliases": ["diva", "diva jn"]},
    "ulh": {"name": "Ulhasnagar (ULH)", "city": "Ulhasnagar", "code": "ULH", "lat": 19.2183, "lng": 73.1558, "aliases": ["ulhasnagar", "ulh"]},
    "bkl": {"name": "Belapur CBD (BKL)", "city": "Belapur", "code": "BKL", "lat": 19.0223, "lng": 73.0314, "aliases": ["belapur", "bkl", "cbd belapur"]},
    "kp": {"name": "Khopoli (KP)", "city": "Khopoli", "code": "KP", "lat": 18.7884, "lng": 73.3420, "aliases": ["khopoli", "kp"]},
    "pbh": {"name": "Parbhani Jn. (PBH)", "city": "Parbhani", "code": "PBH", "lat": 19.2695, "lng": 76.7710, "aliases": ["parbhani", "pbh"]},
    "ltr": {"name": "Latur (LUR)", "city": "Latur", "code": "LUR", "lat": 18.4088, "lng": 76.5604, "aliases": ["latur", "lur"]},
    "snsi": {"name": "Sangli (SNSI)", "city": "Sangli", "code": "SNSI", "lat": 16.8524, "lng": 74.5815, "aliases": ["sangli", "snsi"]},
    "miraj": {"name": "Miraj Jn. (MRJ)", "city": "Miraj", "code": "MRJ", "lat": 16.8259, "lng": 74.6436, "aliases": ["miraj", "mrj", "miraj jn"]},
    "pune_jn": {"name": "Pune Jn. (PUNE)", "city": "Pune", "code": "PUNE", "lat": 18.5289, "lng": 73.8742, "aliases": ["pune jn", "pune junction", "pune station"]},
    "ltt": {"name": "Lokmanya Tilak Terminus (LTT)", "city": "Mumbai", "code": "LTT", "lat": 19.0667, "lng": 72.9269, "aliases": ["ltt", "kurla terminus", "lokmanya tilak terminus", "kurla"]},
    "bct": {"name": "Mumbai Central (BCT)", "city": "Mumbai", "code": "BCT", "lat": 18.9711, "lng": 72.8193, "aliases": ["mumbai central", "bct", "mmct"]},
    "bvi": {"name": "Borivali (BVI)", "city": "Borivali", "code": "BVI", "lat": 19.2322, "lng": 72.8568, "aliases": ["borivali", "bvi"]},
    "andheri": {"name": "Andheri (ADH)", "city": "Mumbai", "code": "ADH", "lat": 19.1197, "lng": 72.8468, "aliases": ["andheri", "adh"]},
    # Konkan Railway & Western Regional Corridors
    "rn": {"name": "Ratnagiri (RN)", "city": "Ratnagiri", "code": "RN", "lat": 16.9902, "lng": 73.3120, "aliases": ["ratnagiri", "rn", "ratnagiri jn"]},
    "chi": {"name": "Chiplun (CHI)", "city": "Chiplun", "code": "CHI", "lat": 17.5323, "lng": 73.5186, "aliases": ["chiplun", "chi"]},
    "kkw": {"name": "Kankavali (KKW)", "city": "Kankavali", "code": "KKW", "lat": 16.2736, "lng": 73.7128, "aliases": ["kankavali", "kankavli", "kkw"]},
    "kudl": {"name": "Kudal (KUDL)", "city": "Kudal", "code": "KUDL", "lat": 16.0108, "lng": 73.6874, "aliases": ["kudal", "kudl"]},
    "swv": {"name": "Sawantwadi Road (SWV)", "city": "Sawantwadi", "code": "SWV", "lat": 15.9080, "lng": 73.8183, "aliases": ["sawantwadi", "swv", "sawantwadi road"]},
    "krmi": {"name": "Karmali (KRMI)", "city": "Karmali", "code": "KRMI", "lat": 15.5173, "lng": 73.9189, "aliases": ["karmali", "krmi", "old goa"]},
    "khed": {"name": "Khed (KHED)", "city": "Khed", "code": "KHED", "lat": 17.7188, "lng": 73.3934, "aliases": ["khed"]},
    "roha": {"name": "Roha (ROHA)", "city": "Roha", "code": "ROHA", "lat": 18.4357, "lng": 73.1197, "aliases": ["roha", "roha jn"]},
    # Global Airports (only major hubs with real flight connections from India)
    "lhr": {"name": "London (LHR)", "city": "London", "code": "LHR", "lat": 51.4700, "lng": -0.4543, "aliases": ["london", "lhr", "heathrow", "gatwick", "lgw"]},
    "zrh": {"name": "Zurich (ZRH)", "city": "Zurich", "code": "ZRH", "lat": 47.4582, "lng": 8.5555, "aliases": ["zurich", "zrh"]},
    "gva": {"name": "Geneva (GVA)", "city": "Geneva", "code": "GVA", "lat": 46.2370, "lng": 6.1092, "aliases": ["geneva", "gva"]},
    "cdg": {"name": "Paris (CDG)", "city": "Paris", "code": "CDG", "lat": 49.0097, "lng": 2.5479, "aliases": ["paris", "cdg", "ory"]},
    "fra": {"name": "Frankfurt (FRA)", "city": "Frankfurt", "code": "FRA", "lat": 50.0379, "lng": 8.5622, "aliases": ["frankfurt", "fra"]},
    "muc": {"name": "Munich (MUC)", "city": "Munich", "code": "MUC", "lat": 48.3537, "lng": 11.7750, "aliases": ["munich", "muc"]},
    "dxb": {"name": "Dubai (DXB)", "city": "Dubai", "code": "DXB", "lat": 25.2532, "lng": 55.3657, "aliases": ["dubai", "dxb"]},
    "sin": {"name": "Singapore (SIN)", "city": "Singapore", "code": "SIN", "lat": 1.3644, "lng": 103.9915, "aliases": ["singapore", "sin", "changi"]},
    "bkk": {"name": "Bangkok (BKK)", "city": "Bangkok", "code": "BKK", "lat": 13.6900, "lng": 100.7501, "aliases": ["bangkok", "bkk", "suvarnabhumi"]},
    "jfk": {"name": "New York (JFK)", "city": "New York", "code": "JFK", "lat": 40.6413, "lng": -73.7781, "aliases": ["new york", "jfk", "nyc", "newark", "ewr"]},
    "sfo": {"name": "San Francisco (SFO)", "city": "San Francisco", "code": "SFO", "lat": 37.6213, "lng": -122.3790, "aliases": ["san francisco", "sfo"]},
    "lax": {"name": "Los Angeles (LAX)", "city": "Los Angeles", "code": "LAX", "lat": 33.9416, "lng": -118.4085, "aliases": ["los angeles", "lax"]},
    "hnd": {"name": "Tokyo (HND)", "city": "Tokyo", "code": "HND", "lat": 35.5494, "lng": 139.7798, "aliases": ["tokyo", "hnd", "haneda", "narita", "nrt"]}
}

def lookup_location(query: str) -> Optional[Dict[str, Any]]:
    """Intelligently matches a location name, airport name, or station/IATA code against KNOWN_LOCATIONS."""
    if not query or not isinstance(query, str):
        return None
    raw_str = query.strip()
    clean_q = re.sub(r'[^a-zA-Z0-9\s]', ' ', raw_str).strip().lower()
    if not clean_q:
        return None

    # 1. Exact alias match, key match, or station/airport code match
    for key, loc in KNOWN_LOCATIONS.items():
        loc_code = loc["code"].lower()
        if clean_q in loc["aliases"] or clean_q == key or clean_q == loc_code:
            return loc

    # 2. Station or airport code in parentheses, e.g. "Ratnagiri (RN)" or "Panvel (PNVL)"
    code_match = re.search(r'\(([a-zA-Z]{2,5})\)', raw_str)
    if code_match:
        cand_code = code_match.group(1).lower()
        for key, loc in KNOWN_LOCATIONS.items():
            if cand_code == loc["code"].lower() or cand_code == key or cand_code in loc["aliases"]:
                return loc

    # 3. Token-level match with word boundary (allowing 2-letter station codes like 'rn', 'st', 'et', 'vr')
    stop_words = {"to", "in", "at", "on", "by", "of", "is", "or", "me", "my", "we", "he", "it", "so", "as", "no", "an", "am", "pm", "the", "for", "from", "and"}
    tokens = [t for t in clean_q.split() if t not in stop_words]
    for tok in tokens:
        for key, loc in KNOWN_LOCATIONS.items():
            if tok == loc["code"].lower() or tok == key:
                return loc
            if len(tok) >= 3 and tok in loc["aliases"]:
                return loc
            elif len(tok) == 2 and tok in loc["aliases"] and tok not in stop_words:
                return loc

    # 4. Strict whole-word substring match for longer city names (>= 4 characters)
    # Note: NEVER do `clean_q in alias` (prevents 'rn' falsely matching 'suvarnabhumi')!
    for key, loc in KNOWN_LOCATIONS.items():
        for alias in loc["aliases"]:
            if len(alias) >= 4:
                if re.search(rf'\b{re.escape(alias)}\b', clean_q):
                    return loc

    return None

def is_consistent_match(raw_text: str, match_loc: Optional[Dict[str, Any]]) -> bool:
    """Validates that a resolved location candidate shares genuine tokens, station code, or city with raw extracted text."""
    if not match_loc or not raw_text:
        return False
    raw_lower = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(raw_text)).lower()
    raw_tokens = set(raw_lower.split())
    code = match_loc.get("code", "").lower()
    city = match_loc.get("city", "").lower()
    aliases = [a.lower() for a in match_loc.get("aliases", [])]

    if code and (code in raw_tokens or code in raw_lower):
        return True
    if city and (city in raw_tokens or city in raw_lower):
        return True
    for a in aliases:
        if len(a) >= 3 and (a in raw_tokens or a in raw_lower):
            return True
    return False

def detect_locations_from_text(text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Finds origin and destination from document text using strict word boundaries
    and directional travel patterns to prevent false substring collisions (e.g. 'del' inside 'delayed').
    """
    text_lower = text.lower()
    
    # 1. Check explicit directional travel patterns (e.g. 'Sector: BLR - HYD', 'From: Bengaluru To: Hyderabad', 'Ratnagiri → Panvel')
    directional_patterns = [
        r'(?:sector|route|flight|journey)\s*[:\-]?\s*([a-zA-Z\s\(\)]{3,30}?)\s*(?:to|➔|->|→|⟶|--|-)\s*([a-zA-Z\s\(\)]{3,30})',
        r'(?:from|departure|departing|origin|originating|boarding)\s*[:\-]?\s*([a-zA-Z\s\(\)]{3,30}?)\s*(?:to|arrival|arriving|dest|destination|deboarding)\s*[:\-]?\s*([a-zA-Z\s\(\)]{3,30})',
        r'\b([a-zA-Z]{3,15})\s*(?:to|➔|->|→|⟶)\s*([a-zA-Z]{3,15})\b'
    ]

    for pat in directional_patterns:
        match = re.search(pat, text, re.IGNORECASE) or re.search(pat, text_lower)
        if match:
            cand1 = match.group(1).strip()
            cand2 = match.group(2).strip()
            loc1 = lookup_location(cand1)
            loc2 = lookup_location(cand2)
            if loc1 and loc2 and loc1["name"] != loc2["name"]:
                return loc1, loc2

    # 2. Scan for occurring locations using STRICT WORD BOUNDARIES \b...\b
    occurrences: List[Tuple[int, Dict[str, Any]]] = []
    for key, loc in KNOWN_LOCATIONS.items():
        for alias in loc["aliases"]:
            # For short 1-2 char aliases (like codes 'rn', 'st', 'et', 'r'), require uppercase in raw text
            if len(alias) <= 2:
                pattern = rf'\b{re.escape(alias.upper())}\b'
                for m in re.finditer(pattern, text):
                    occurrences.append((m.start(), loc))
            else:
                pattern = rf'\b{re.escape(alias)}\b'
                for m in re.finditer(pattern, text_lower):
                    occurrences.append((m.start(), loc))

    # Sort sequentially by order of appearance in the document
    occurrences.sort(key=lambda x: x[0])
    
    unique_locs: List[Dict[str, Any]] = []
    seen_names = set()
    for _, loc in occurrences:
        if loc["name"] not in seen_names:
            seen_names.add(loc["name"])
            unique_locs.append(loc)

    if len(unique_locs) >= 2:
        return unique_locs[0], unique_locs[1]
    elif len(unique_locs) == 1:
        single = unique_locs[0]
        default_pair = KNOWN_LOCATIONS["del"] if single["name"] != KNOWN_LOCATIONS["del"]["name"] else KNOWN_LOCATIONS["bom"]
        return single, default_pair

    # Default fallback
    return KNOWN_LOCATIONS["bom"], KNOWN_LOCATIONS["del"]

def extract_ticket_with_ai(extracted_text: str, filename: str, file_bytes: bytes, content_type: str) -> Optional[Dict[str, Any]]:
    """
    Leverages Gemini 2.5 Flash / Groq LLMs to accurately extract structured travel parameters
    from tickets, boarding passes, and booking confirmations.
    """
    prompt = f"""You are a specialized travel ticket parsing engine.
Extract the following travel parameters from this uploaded travel document in STRICT JSON format:
{{
  "carrier": "airline, railway, or bus operator name (e.g. IndiGo, Air India, Indian Railways, British Airways, etc.)",
  "service_number": "flight or train number (e.g. 6E 521, AI 882, #20978, 11026, BA 712)",
  "origin": "origin city and airport or station name with code (e.g. Amravati (AMI), Bhusaval (BSL), Bangalore (BLR), Mumbai (BOM), Delhi (DEL))",
  "destination": "destination city and airport or station name with code (e.g. Bhusaval (BSL), Hyderabad (HYD), Jaipur (JAI), Delhi (DEL))",
  "origin_code": "3-letter IATA code or station code (e.g. AMI, BSL, BLR, HYD, DEL, BOM, JAI)",
  "destination_code": "3-letter IATA code or station code (e.g. BSL, AMI, HYD, JAI, DEL, BOM)",
  "travel_date": "Date of journey string in YYYY-MM-DD, DD/MM/YYYY, or DD-Mon-YYYY format if found (e.g. 2024-09-24, 24-09-2024, or 24-Sep-2024)",
  "is_past_journey": true if the travel date or journey date is before today or in a past year (e.g. 2024, 2025, or earlier date), false otherwise,
  "scheduled_departure": "scheduled departure time string if available (e.g. 14:30)",
  "scheduled_arrival": "scheduled arrival time string if available (e.g. 16:45)",
  "delay_minutes": 0,
  "is_cancellation": false,
  "passenger_name": "Full name of passenger / traveler if printed on document, or null",
  "pnr": "PNR or booking reference number (e.g. VY-88291 or 10-digit IRCTC PNR code)",
  "ticket_cost": 1250.0,
  "currency": "INR",
  "disruption_reason": "brief reason for delay or cancellation if explicitly mentioned, or Nominal Operation"
}}

IMPORTANT:
- Ensure origin and destination are the actual cities/airports/stations indicated in the ticket.
- Do NOT guess Mumbai or Delhi unless specifically mentioned in the ticket.
- Default delay_minutes to 0 unless an operational delay is explicitly stated.
- Return ONLY valid JSON, no markdown formatting or commentary.

Document Filename: {filename}
Document Content:
\"\"\"
{extracted_text[:4000]}
\"\"\"
"""
    # 1. Try Gemini with multi-key failover
    gem_keys = get_gemini_keys()
    if gem_keys and genai is not None:
        for gk in gem_keys:
            try:
                genai.configure(api_key=gk)
                # Use cheapest Gemini model for ticket parsing
                model = genai.GenerativeModel("gemini-3.1-flash-lite")
                response = model.generate_content(prompt)
                if response and response.text:
                    raw = response.text.strip()
                    if raw.startswith("```"):
                        raw = re.sub(r'^```(?:json)?\n', '', raw)
                        raw = re.sub(r'\n```$', '', raw)
                    data = json.loads(raw)
                    if isinstance(data, dict) and data.get("origin") and data.get("destination"):
                        return data
            except Exception:
                continue

    # 2. Try Groq with multi-key failover
    gr_keys = get_groq_keys()
    if gr_keys and Groq is not None:
        for qk in gr_keys:
            try:
                client = Groq(api_key=qk)
                completion = client.chat.completions.create(
                    model="qwen/qwen3.8-27b",
                    messages=[
                        {"role": "system", "content": "You are a ticket extraction parser. Output strict JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=1000
                )
                raw = completion.choices[0].message.content.strip()
                if raw.startswith("```"):
                    raw = re.sub(r'^```(?:json)?\n', '', raw)
                    raw = re.sub(r'\n```$', '', raw)
                data = json.loads(raw)
                if isinstance(data, dict) and data.get("origin") and data.get("destination"):
                    return data
            except Exception:
                continue

    return None

def parse_document_file(file_bytes: bytes, filename: str = "ticket.pdf", content_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Parses real document file (PDF, TXT, Image), extracts authentic travel details
    using AI vision/structured extraction with rigorous geospatial fallback,
    detects historical dates/completed journeys, and stores structured record in SQLite.
    """
    extracted_text = ""
    safe_fn = (filename or "ticket.pdf").lower()
    safe_ct = (content_type or "").lower()

    # Determine if file is PDF
    is_pdf = safe_fn.endswith(".pdf") or ("pdf" in safe_ct and not safe_fn.endswith((".txt", ".json", ".csv")))

    if is_pdf and pypdf is not None:
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                txt = page.extract_text()
                if txt:
                    extracted_text += txt + "\n"
        except Exception:
            try:
                extracted_text = file_bytes.decode("utf-8", errors="ignore")
            except Exception:
                extracted_text = ""
    else:
        try:
            extracted_text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            extracted_text = f"Binary file {filename}"

    combined_text = extracted_text + " " + filename
    lower = combined_text.lower()

    # 1. Attempt AI extraction first (Gemini 2.5 Flash / Groq)
    ai_data = extract_ticket_with_ai(extracted_text, filename, file_bytes, content_type or "application/pdf")

    travel_date_str = None
    is_past_journey = False

    if ai_data:
        carrier = ai_data.get("carrier") or "Carrier"
        service_number = ai_data.get("service_number") or "Transit Link"
        raw_origin = ai_data.get("origin") or "Origin"
        raw_destination = ai_data.get("destination") or "Destination"
        travel_date_str = ai_data.get("travel_date")
        if ai_data.get("is_past_journey") is True:
            is_past_journey = True
        
        delay_val = ai_data.get("delay_minutes")
        try:
            delay_minutes = int(delay_val) if delay_val is not None else 0
        except (ValueError, TypeError):
            delay_minutes = 0

        is_cancellation = bool(ai_data.get("is_cancellation", False))
        pnr = ai_data.get("pnr") or f"VY-{int(datetime.now().timestamp()) % 100000:05d}-IN"
        
        cost_val = ai_data.get("ticket_cost")
        try:
            ticket_cost = float(cost_val) if cost_val is not None else (1250.0 if "rail" in carrier.lower() or "train" in carrier.lower() else 4850.0)
        except (ValueError, TypeError):
            ticket_cost = 1250.0

        currency = ai_data.get("currency") or "INR"
        reason = ai_data.get("disruption_reason") or (f"Operational delay on {service_number}" if delay_minutes > 0 else "Nominal on-schedule operation")

        # Resolve genuine coordinates from extracted locations
        orig_match = lookup_location(ai_data.get("origin_code") or raw_origin)
        dest_match = lookup_location(ai_data.get("destination_code") or raw_destination)

        # Discard false positive matches that don't match the authentic raw ticket text
        if orig_match and not is_consistent_match(raw_origin, orig_match) and not is_consistent_match(ai_data.get("origin_code", ""), orig_match):
            orig_match = None
        if dest_match and not is_consistent_match(raw_destination, dest_match) and not is_consistent_match(ai_data.get("destination_code", ""), dest_match):
            dest_match = None

        # CRITICAL: Preserve authentic ticket text extracted by AI vision/OCR
        if raw_origin and raw_origin.strip() not in ["Origin", "Departure", "From", "Unknown", ""]:
            origin_name = orig_match["name"] if (orig_match and orig_match["name"] != "Origin") else raw_origin.strip()
        elif orig_match:
            origin_name = orig_match["name"]
        else:
            origin_name = "Origin"

        if raw_destination and raw_destination.strip() not in ["Destination", "Arrival", "To", "Unknown", ""]:
            dest_name = dest_match["name"] if (dest_match and dest_match["name"] != "Destination") else raw_destination.strip()
        elif dest_match:
            dest_name = dest_match["name"]
        else:
            dest_name = "Destination"

        origin_coords = {"lat": orig_match["lat"], "lng": orig_match["lng"]} if orig_match else {"lat": 16.9902, "lng": 73.3120}
        dest_coords = {"lat": dest_match["lat"], "lng": dest_match["lng"]} if dest_match else {"lat": 18.9943, "lng": 73.1104}
    else:
        # 2. Heuristic Regex Fallback with Strict Word Boundaries
        origin_loc, dest_loc = detect_locations_from_text(combined_text)
        origin_name = origin_loc["name"]
        dest_name = dest_loc["name"]
        origin_coords = {"lat": origin_loc["lat"], "lng": origin_loc["lng"]}
        dest_coords = {"lat": dest_loc["lat"], "lng": dest_loc["lng"]}

        # Check for Train (Indian Railways / RailRadar)
        train_num_match = re.search(r'\b(1\d{4}|2\d{4}|12\d{3}|20\d{3}|22\d{3})\b', lower)
        is_train = bool(train_num_match) or any(k in lower for k in ["train", "vande bharat", "railway", "irctc", "express", "shatabdi", "rajdhani", "ami", "bsl"])

        if is_train:
            carrier = "Indian Railways"
            if train_num_match:
                train_num = train_num_match.group(1)
                # Fetch train name only — do NOT inherit live delay for uploaded tickets
                try:
                    t_data = RailRadarTracker.get_live_train_status(train_num)
                    train_name = t_data.get("train_name", "Express")
                    if not origin_loc and t_data.get("origin"):
                        origin_name = t_data.get("origin")
                    if not dest_loc and t_data.get("destination"):
                        dest_name = t_data.get("destination")
                except Exception:
                    train_name = "Express"
                service_number = f"#{train_num} {train_name}"
            else:
                service_number = "Indian Railways Express"
            mode = "train"
        else:
            mode = "flight"
            carrier = "Airline"
            if "air india" in lower or "airindia" in lower or "air-india" in lower: carrier = "Air India"
            elif "indigo" in lower or "6e" in lower: carrier = "IndiGo"
            elif "spicejet" in lower or "sg" in lower: carrier = "SpiceJet"
            elif "vistara" in lower or "uk" in lower: carrier = "Vistara"
            elif "british" in lower or "ba" in lower: carrier = "British Airways"
            elif "swiss" in lower or "lx" in lower: carrier = "SWISS"
            elif "lufthansa" in lower or "lh" in lower: carrier = "Lufthansa"
            elif "emirates" in lower or "ek" in lower: carrier = "Emirates"

            service_match = re.search(r'\b(6e|ai|sg|uk|ba|aa|dl|lx|lh|ek)[\s-]?(\d{2,4})\b', lower)
            if service_match:
                service_number = f"{service_match.group(1).upper()} {service_match.group(2)}"
            else:
                service_number = f"{carrier} Flight"

        # PNR extraction
        pnr_match = re.search(r'\bpnr[\s:=-]+([a-z0-9]{6,10})\b', lower)
        pnr = f"VY-{pnr_match.group(1).upper()}" if pnr_match else f"VY-{int(datetime.now().timestamp()) % 100000:05d}-IN"

        # Delay extraction — ONLY from explicit text in the document. Default is always 0.
        is_cancellation = "cancel" in lower or "cancelled" in lower
        delay_minutes = 0  # No delay unless explicitly stated in the ticket
        delay_match = re.search(r'(\d+)\s*(mins?|minutes?|hrs?|hours?)\s*(?:delay|late)', lower)
        if delay_match:
            val = int(delay_match.group(1))
            unit = delay_match.group(2)
            delay_minutes = val * 60 if "hr" in unit else val
        elif is_cancellation:
            delay_minutes = 360

        # Fare extraction
        fare_match = re.search(r'(?:rs\.?|inr|₹|\$|€|£)\s*([\d,]+(?:\.\d{2})?)', lower)
        ticket_cost = 0.0
        if fare_match:
            try:
                ticket_cost = float(fare_match.group(1).replace(",", ""))
            except Exception:
                pass
        currency = "INR"
        reason = f"Operational Delay on {service_number}" if delay_minutes > 0 else ("Service Cancellation" if is_cancellation else "Nominal on-schedule operation")

    # Date extraction & past journey detection
    try:
        import dateutil.parser
        _has_dateutil = True
    except ImportError:
        _has_dateutil = False

    if not travel_date_str:
        d_match = re.search(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b', combined_text)
        if d_match:
            travel_date_str = d_match.group(0)
        else:
            d_match2 = re.search(r'\b(\d{1,2})\s*[-/ ]\s*(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*[-/ ]\s*(\d{2,4})\b', combined_text, re.IGNORECASE)
            if d_match2:
                travel_date_str = d_match2.group(0)
            else:
                d_match3 = re.search(r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),?\s+(\d{4})\b', combined_text, re.IGNORECASE)
                if d_match3:
                    travel_date_str = d_match3.group(0)

    if travel_date_str:
        parsed_date = False
        if _has_dateutil:
            try:
                dt_obj = dateutil.parser.parse(str(travel_date_str).strip(), fuzzy=True)
                if dt_obj.year < 100:
                    dt_obj = dt_obj.replace(year=2000 + dt_obj.year)
                if dt_obj.date() < datetime.now().date():
                    is_past_journey = True
                parsed_date = True
            except Exception:
                pass
        if not parsed_date:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d-%b-%Y", "%d %b %Y", "%d %B %Y"):
                try:
                    dt_obj = datetime.strptime(str(travel_date_str).strip(), fmt)
                    if dt_obj.year < 100:
                        dt_obj = dt_obj.replace(year=2000 + dt_obj.year)
                    if dt_obj.date() < datetime.now().date():
                        is_past_journey = True
                    break
                except Exception:
                    pass

    # Only check for past years if a date was explicitly parsed from the travel_date field,
    # NOT from raw document text (avoids false positives on fares like ₹2,024 or PNR containing 2024)
    # This check is now based only on the AI-extracted travel_date_str or the parsed date object
    if not is_past_journey and travel_date_str:
        # Check if the parsed date string explicitly contains a past year
        year_in_date = re.search(r'\b(20[0-2]\d)\b', str(travel_date_str))
        if year_in_date:
            try:
                yr = int(year_in_date.group(1))
                if yr < datetime.now().year:
                    is_past_journey = True
            except ValueError:
                pass

    # Check for keywords indicating completed or yesterday journey
    if any(k in lower for k in ["yesterday", "completed", "past journey", "chart prepared", "traveled on", "historical", "already run"]):
        is_past_journey = True

    journey_status = "COMPLETED" if is_past_journey else ("CANCELLED" if is_cancellation else ("DELAYED" if delay_minutes > 15 else "ON_TIME"))
    if is_past_journey:
        reason = f"Historical Journey ({travel_date_str or 'Past date'}): Service already completed run"

    # Extract passenger name from AI data or document text
    extracted_pax = ai_data.get("passenger_name") if ai_data else None
    if not extracted_pax or str(extracted_pax).strip().lower() in ["passenger", "unknown", "n/a", "null", "none", ""]:
        pax_regex = re.search(r'(?:passenger|traveler|traveller|name|pax)\s*(?:name)?[\s:=-]+([A-Za-z\s]{2,30})', combined_text, re.IGNORECASE)
        if pax_regex:
            cand = pax_regex.group(1).strip()
            if not any(stopw in cand.lower() for stopw in ["pnr", "ticket", "date", "class", "seat", "coach", "train", "flight", "terminal", "service", "status"]):
                extracted_pax = cand.title()
    passenger_name = extracted_pax or "Passenger"

    # Build and persist disruption record with verified coordinates & past journey metadata
    disruption_record = {
        "pnr": pnr,
        "passenger_name": passenger_name,
        "booking_source": f"Parsed Ticket ({filename})",
        "carrier": carrier,
        "service_number": service_number,
        "origin": origin_name,
        "destination": dest_name,
        "origin_coords": origin_coords,
        "dest_coords": dest_coords,
        "travel_date": travel_date_str or datetime.now().strftime("%Y-%m-%d"),
        "is_past_journey": is_past_journey,
        "journey_status": journey_status,
        "delay_minutes": delay_minutes,
        "is_cancellation": is_cancellation,
        "disruption_reason": reason,
        "ticket_cost": ticket_cost,
        "currency": currency
    }

    saved_data = save_external_disruption(disruption_record)

    return {
        "status": "SUCCESSFULLY_PARSED_AND_STORED",
        "filename": filename,
        "text_preview": extracted_text[:300] if extracted_text else "Binary document processed",
        "structured_data": saved_data
    }

