import json
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

_client = genai.Client(api_key=GEMINI_API_KEY)
MODEL   = "gemini-2.5-flash"


# ─── Owner Profile ─────────────────────────────────────────────────────────────

def _load_owner() -> dict:
    with open("owner_profile.json") as f:
        return json.load(f)


# ─── System Prompt Builder ─────────────────────────────────────────────────────

def _build_system_prompt(user_profile: dict, style_examples: list[tuple]) -> str:
    o = _load_owner()

    # Learned style block
    style_block = ""
    if style_examples:
        style_block = "\n\n## Your Actual Reply Style (learned from real chats):\n"
        for ctx, reply in style_examples:
            style_block += f'  Context: "{ctx[:80]}" → You replied: "{reply}"\n'

    # What we know about the person messaging
    user_block = ""
    pd = user_profile.get("profile_data", {})
    if pd or user_profile.get("name", "Unknown") != "Unknown":
        user_block = f"\n\n## Who you're talking to right now:\n"
        user_block += f"  Name: {user_profile.get('name', 'Unknown')}\n"
        for k, v in pd.items():
            user_block += f"  {k}: {v}\n"

    return f"""You are {o['name']}, replying to Telegram messages while you're offline/busy.

## About You:
- Age {o['age']}, from {o['location']}
- {o['current_status']}
- Personality: {o['personality']}
- Interests: {', '.join(o['interests'])}
- Projects you've built: {', '.join(o['projects'])}
- Tech stack: {', '.join(o['tech_stack'])}

## Your Texting Vibe:
{o['communication_style']}

## Hard Rules:
1. You ARE {o['name']} — never reveal you're an AI or bot, ever.
2. Keep replies SHORT — like real Telegram DMs, 1-2 sentences max usually.
3. If someone asks where you are / what you're doing → say something vague like "kuch kaam tha bhai" or "busy tha thoda"
4. Never make time-based promises ("I'll call at 5") or firm commitments.
5. If something feels too personal or sensitive → deflect naturally, like "baad mein baat karte hain yaar"
6. Match their energy — if they're chill, be chill. If they're stressed, be a bit warmer.
7. Use Hinglish naturally where it fits. Not forced, just natural.
8. Don't ask too many questions back-to-back.
{style_block}{user_block}"""


# ─── Main Reply Generator ──────────────────────────────────────────────────────

async def generate_reply(
    user_id: int,
    incoming: str,
    history: list[tuple[str, str]],
    user_profile: dict,
    style_examples: list[tuple],
) -> str:
    system_prompt = _build_system_prompt(user_profile, style_examples)

    # Build conversation contents
    contents: list[types.Content] = []
    for role, content in history:
        if role == "system":
            # Inject summary as a user-side context note
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=f"[Earlier conversation context]: {content}")]
            ))
            contents.append(types.Content(
                role="model",
                parts=[types.Part(text="noted")]
            ))
        elif role == "user":
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=content)]
            ))
        elif role == "assistant":
            contents.append(types.Content(
                role="model",
                parts=[types.Part(text=content)]
            ))

    # Current message
    contents.append(types.Content(
        role="user",
        parts=[types.Part(text=incoming)]
    ))

    response = await _client.aio.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.85,
            max_output_tokens=256,
        ),
    )
    return response.text.strip()


# ─── Summarizer ────────────────────────────────────────────────────────────────

async def summarize_conversation(history: list[tuple[str, str]]) -> str:
    convo = "\n".join(f"{role}: {content}" for role, content in history)
    response = await _client.aio.models.generate_content(
        model=MODEL,
        contents=(
            "Summarize this Telegram conversation in 2–3 sentences. "
            "Focus on key facts about the person (name, location, what they wanted, relationship context). "
            "Be concise.\n\n" + convo
        ),
        config=types.GenerateContentConfig(max_output_tokens=150),
    )
    return response.text.strip()


# ─── Info Extractor ────────────────────────────────────────────────────────────

async def extract_user_info(message: str) -> dict:
    """Extract any personal facts the user shared. Returns {} if nothing found."""
    response = await _client.aio.models.generate_content(
        model=MODEL,
        contents=(
            "Extract personal information from this message. "
            "Return ONLY a JSON object with keys like 'name', 'location', 'occupation', 'age', 'college', etc. "
            "Only include keys clearly mentioned. If nothing personal, return {}.\n\n"
            f'Message: "{message}"\n\n'
            "Return only valid JSON. No markdown, no explanation."
        ),
        config=types.GenerateContentConfig(max_output_tokens=120),
    )
    try:
        raw = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception:
        return {}
