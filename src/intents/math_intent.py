"""
math_intent.py — Offline Hindi/Hinglish Math Calculator
=========================================================
Parses Hindi/Hinglish speech text to extract two numbers and an operator,
performs the calculation, and returns a Hindi result string.

Supported operations:
  + : जोड़, प्लस, और, plus, add, jod, jodo, jodan
  - : घटाओ, माइनस, घटा, minus, minus, ghatao, ghata
  × : गुणा, गुणित, बार, times, multiply, guna, x
  ÷ : भाग, divided, divide, bhaag, per, बटा, bata

Supported number forms:
  • Hindi words:  एक, दो, तीन … नब्बे, सौ, हजार
  • Hinglish:     ek, do, teen, char, paanch …
  • Digits:       1, 2, 3 … 999

Returns:
  extract_math_intent(text) → dict | None
    {
      "num1":     float,
      "num2":     float,
      "op":       "add" | "sub" | "mul" | "div",
      "result":   float,
      "answer":   str,   # Hindi TTS string e.g. "उत्तर 12 है"
      "equation": str,   # e.g. "5 + 7 = 12"
    }
  Returns None if text is not a math command.
"""

import re

# ─────────────────────────────────────────────────────────────────────────────
# Number word → value mapping  (Hindi + Hinglish + English)
# ─────────────────────────────────────────────────────────────────────────────

NUMBER_WORDS: dict[str, float] = {
    # ── zero ──
    "शून्य": 0, "zero": 0, "sifar": 0, "सिफर": 0,
    # ── 1-9 ──
    "एक": 1,   "ek": 1,    "one": 1,
    "दो": 2,   "do": 2,    "two": 2,
    "तीन": 3,  "teen": 3,  "three": 3,
    "चार": 4,  "char": 4,  "four": 4,
    "पांच": 5, "पाँच": 5,  "paanch": 5, "panch": 5, "five": 5,
    "छह": 6,   "chhe": 6,  "chhah": 6,  "six": 6,
    "सात": 7,  "saat": 7,  "seven": 7,
    "आठ": 8,   "aath": 8,  "eight": 8,
    "नौ": 9,   "nau": 9,   "nine": 9,
    # ── 10-19 ──
    "दस": 10,     "das": 10,     "ten": 10,
    "ग्यारह": 11, "gyarah": 11,  "eleven": 11,
    "बारह": 12,   "barah": 12,   "twelve": 12,
    "तेरह": 13,   "terah": 13,   "thirteen": 13,
    "चौदह": 14,   "chaudah": 14, "fourteen": 14,
    "पंद्रह": 15, "pandrah": 15, "fifteen": 15,
    "सोलह": 16,   "solah": 16,   "sixteen": 16,
    "सत्रह": 17,  "satrah": 17,  "seventeen": 17,
    "अठारह": 18,  "atharah": 18, "eighteen": 18,
    "उन्नीस": 19, "unnees": 19,  "nineteen": 19,
    # ── 20-99 (tens) ──
    "बीस": 20,    "bees": 20,    "twenty": 20,
    "इक्कीस": 21, "ikkees": 21,  "twenty one": 21,
    "बाईस": 22,   "baees": 22,   "twenty two": 22,
    "तेईस": 23,   "tees": 23,
    "चौबीस": 24,  "chaubees": 24,
    "पच्चीस": 25, "pachchees": 25,
    "छब्बीस": 26, "chabbees": 26,
    "सत्ताईस": 27,"sattaees": 27,
    "अट्ठाईस": 28,"atthaees": 28,
    "उनतीस": 29,  "untees": 29,
    "तीस": 30,    "tees": 30,    "thirty": 30,
    "इकतीस": 31,  "iktees": 31,
    "बत्तीस": 32, "battees": 32,
    "तैंतीस": 33, "taintees": 33,
    "चौंतीस": 34, "chauntees": 34,
    "पैंतीस": 35, "paintees": 35,
    "छत्तीस": 36, "chattees": 36,
    "सैंतीस": 37, "saintees": 37,
    "अड़तीस": 38, "adtees": 38,
    "उनतालीस": 39,"untaalees": 39,
    "चालीस": 40,  "chalis": 40,  "forty": 40,
    "इकतालीस": 41,"iktaalees": 41,
    "बयालीस": 42, "bayalees": 42,
    "तैंतालीस": 43,"taintaalees": 43,
    "चवालीस": 44, "chavalees": 44,
    "पैंतालीस": 45,"paintaalees": 45,
    "छियालीस": 46,"chhiyalees": 46,
    "सैंतालीस": 47,"saintaalees": 47,
    "अड़तालीस": 48,"adtaalees": 48,
    "उनचास": 49,  "unchaas": 49,
    "पचास": 50,   "pachaas": 50, "fifty": 50,
    "इक्यावन": 51,"ikyaavan": 51,
    "बावन": 52,   "baavan": 52,
    "तिरपन": 53,  "tirpan": 53,
    "चौवन": 54,   "chauvan": 54,
    "पचपन": 55,   "pachpan": 55,
    "छप्पन": 56,  "chhappan": 56,
    "सत्तावन": 57,"sattaavan": 57,
    "अट्ठावन": 58,"atthaavan": 58,
    "उनसठ": 59,   "unsath": 59,
    "साठ": 60,    "saath": 60,   "sixty": 60,
    "इकसठ": 61,   "iksath": 61,
    "बासठ": 62,   "baasath": 62,
    "तिरसठ": 63,  "tirsath": 63,
    "चौंसठ": 64,  "chaunsath": 64,
    "पैंसठ": 65,  "painsath": 65,
    "छियासठ": 66, "chhiyasath": 66,
    "सड़सठ": 67,  "sadsath": 67,
    "अड़सठ": 68,  "adsath": 68,
    "उनहत्तर": 69,"unhattar": 69,
    "सत्तर": 70,  "sattar": 70,  "seventy": 70,
    "इकहत्तर": 71,"ikhattar": 71,
    "बहत्तर": 72, "bahattar": 72,
    "तिहत्तर": 73,"tihattar": 73,
    "चौहत्तर": 74,"chauhattar": 74,
    "पचहत्तर": 75,"pachhattar": 75,
    "छिहत्तर": 76,"chhihattar": 76,
    "सतहत्तर": 77,"sathattar": 77,
    "अठहत्तर": 78,"athhattar": 78,
    "उनासी": 79,  "unaasi": 79,
    "अस्सी": 80,  "assi": 80,    "eighty": 80,
    "इक्यासी": 81,"ikyaasi": 81,
    "बयासी": 82,  "bayaasi": 82,
    "तिरासी": 83, "tiraasi": 83,
    "चौरासी": 84, "chauraasi": 84,
    "पचासी": 85,  "pachaasi": 85,
    "छियासी": 86, "chhiyaasi": 86,
    "सत्तासी": 87,"sattaasi": 87,
    "अट्ठासी": 88,"atthaasi": 88,
    "नवासी": 89,  "navaasi": 89,
    "नब्बे": 90,  "nabbe": 90,   "ninety": 90,
    "इक्यानवे": 91,"ikyaanave": 91,
    "बानवे": 92,  "baanave": 92,
    "तिरानवे": 93,"tiraanave": 93,
    "चौरानवे": 94,"chauraanave": 94,
    "पचानवे": 95, "pachaanave": 95,
    "छियानवे": 96,"chhiyaanave": 96,
    "सत्तानवे": 97,"sattaanave": 97,
    "अट्ठानवे": 98,"atthaanave": 98,
    "निन्यानवे": 99,"ninyaanave": 99,
    # ── 100, 1000 ──
    "सौ": 100,   "sau": 100,   "hundred": 100,
    "हजार": 1000,"hajar": 1000,"thousand": 1000,
}

# ─────────────────────────────────────────────────────────────────────────────
# Operator keyword sets  (all lowercase)
# ─────────────────────────────────────────────────────────────────────────────

ADD_WORDS = {
    # Hindi
    "जोड़", "जोड़ो", "जोड़ना", "जोड़कर", "जोड़ दो", "जोड़ें",
    "और", "धन", "योग", "प्लस",
    # Hinglish / English
    "plus", "add", "jod", "jodo", "jodan", "jodna", "aur",
    "addition", "sum",
}

SUB_WORDS = {
    # Hindi
    "घटाओ", "घटा", "घटाना", "घटाकर", "घटा दो", "घटाएं",
    "माइनस", "ऋण", "अंतर", "कम",
    # Hinglish / English
    "minus", "ghatao", "ghata", "ghatana", "subtract", "subtraction",
    "difference", "kam",
}

MUL_WORDS = {
    # Hindi
    "गुणा", "गुणित", "गुणा करो", "गुणा दो", "बार",
    "गुणनफल", "गुणांक",
    # Hinglish / English
    "times", "multiply", "multiplication", "guna", "gunna",
    "x", "into", "product",
}

DIV_WORDS = {
    # Hindi
    "भाग", "भाग दो", "भाग करो", "बटा", "विभाजित",
    "भागफल",
    # Hinglish / English
    "divide", "divided", "division", "bhaag", "bata",
    "per", "by",
}

# ─────────────────────────────────────────────────────────────────────────────
# Trigger: must contain at least one operator word to be a math command
# ─────────────────────────────────────────────────────────────────────────────

ALL_OP_WORDS = ADD_WORDS | SUB_WORDS | MUL_WORDS | DIV_WORDS

# Symbols that map directly to operators
OP_SYMBOLS = {"+": "add", "-": "sub", "×": "mul", "÷": "div",
              "*": "mul", "/": "div", "x": "mul"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_number(token: str) -> float | None:
    """
    Try to parse a single token as a number.
    Accepts: digit strings ("42"), float strings ("3.5"),
             Hindi/Hinglish words ("तीन", "teen").
    """
    t = token.strip().lower()
    # Pure digit / float
    try:
        return float(t)
    except ValueError:
        pass
    # Word lookup
    return NUMBER_WORDS.get(t)


def _tokenize(text: str) -> list[str]:
    """
    Lowercase, normalise, split into tokens.
    Keeps Hindi Unicode intact; splits on spaces and common punctuation.
    """
    text = text.lower().strip()
    # Replace common symbols with spaced versions
    for sym, word in [("×", " गुणा "), ("÷", " भाग "), ("+", " plus "),
                      ("-", " minus "), ("*", " multiply "), ("/", " divide ")]:
        text = text.replace(sym, word)
    # Split on whitespace
    return text.split()


def _detect_operator(tokens: list[str], lower: str) -> str | None:
    """
    Return 'add'|'sub'|'mul'|'div' if an operator keyword is found.
    Checks multi-word phrases first, then single tokens.
    """
    # Multi-word operator phrases (check full string)
    multi_ops = [
        (ADD_WORDS, "add"),
        (SUB_WORDS, "sub"),
        (MUL_WORDS, "mul"),
        (DIV_WORDS, "div"),
    ]
    for word_set, op in multi_ops:
        for phrase in sorted(word_set, key=len, reverse=True):  # longest first
            if phrase in lower:
                return op

    # Single-token symbols
    for tok in tokens:
        if tok in OP_SYMBOLS:
            return OP_SYMBOLS[tok]

    return None


def _extract_two_numbers(tokens: list[str]) -> tuple[float | None, float | None]:
    """
    Scan tokens left-to-right and collect up to two numeric values,
    skipping operator/filler words.
    """
    nums: list[float] = []
    for tok in tokens:
        val = _parse_number(tok)
        if val is not None:
            nums.append(val)
            if len(nums) == 2:
                break
    if len(nums) == 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return nums[0], None
    return None, None


def _format_result(val: float) -> str:
    """Return int string if whole number, else 2 decimal places."""
    if val == int(val):
        return str(int(val))
    return f"{val:.2f}"


def _op_symbol(op: str) -> str:
    return {
        "add": "+", "sub": "−", "mul": "×", "div": "÷"
    }.get(op, "?")


# ─────────────────────────────────────────────────────────────────────────────
# Main parser
# ─────────────────────────────────────────────────────────────────────────────

def extract_math_intent(text: str) -> dict | None:
    """
    Parse Hindi/Hinglish text for a math command.

    Returns a result dict or None if no math intent found.

    Result dict keys:
        num1, num2   : float
        op           : 'add'|'sub'|'mul'|'div'
        result       : float
        answer       : Hindi TTS string
        equation     : human-readable equation string
    """
    lower  = text.lower().strip()
    tokens = _tokenize(text)

    # ── Gate: must contain an operator keyword ────────────────────────────────
    op = _detect_operator(tokens, lower)
    if op is None:
        return None

    # ── Extract numbers ───────────────────────────────────────────────────────
    num1, num2 = _extract_two_numbers(tokens)

    if num1 is None:
        return {
            "num1": None, "num2": None, "op": op,
            "result": None,
            "answer": "कृपया संख्या दोबारा बोलें।",
            "equation": "? ? ?",
        }

    if num2 is None:
        return {
            "num1": num1, "num2": None, "op": op,
            "result": None,
            "answer": "दूसरी संख्या समझ नहीं आई। दोबारा बोलें।",
            "equation": f"{num1} {_op_symbol(op)} ?",
        }

    # ── Calculate ─────────────────────────────────────────────────────────────
    try:
        if op == "add":
            result = num1 + num2
        elif op == "sub":
            result = num1 - num2
        elif op == "mul":
            result = num1 * num2
        elif op == "div":
            if num2 == 0:
                return {
                    "num1": num1, "num2": 0, "op": "div",
                    "result": None,
                    "answer": "शून्य से भाग संभव नहीं।",
                    "equation": f"{int(num1)} ÷ 0 = ∞",
                }
            result = num1 / num2
        else:
            return None
    except Exception:
        return None

    result_str = _format_result(result)
    equation   = f"{_format_result(num1)} {_op_symbol(op)} {_format_result(num2)} = {result_str}"
    answer     = f"उत्तर {result_str} है।"

    print(f"🧮 Math: {equation}  (from: '{text}')")

    return {
        "num1":     num1,
        "num2":     num2,
        "op":       op,
        "result":   result,
        "answer":   answer,
        "equation": equation,
    }
