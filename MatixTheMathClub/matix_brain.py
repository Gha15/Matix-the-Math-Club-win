#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================================
 MATIX BRAIN v1.0 - Matix the Math Club's very own AI
 100% Python. 0% external AI. 0 API keys. Built for Ghadi's club.
=====================================================================
HOW TO START
  1) Install Python 3.9+ from python.org
  2) Double-click start_windows.bat (Windows) or start_mac.command (Mac)
     ...or run:  python3 matix_brain.py
  3) It prints your Brain address, e.g.  http://192.168.1.20:8787
  4) In the club app: AI tab -> optional settings -> Club Brain address
     -> paste it -> Save. The owner saving it shares it with every member.

WHAT IT DOES (all in this one file, all Python)
  * Chats and answers questions with its own brain
    (intent engine + naive bayes + a tiny neural network trained at boot)
  * Solves real math step by step: 3x+5=20, x^2-5x+6=0, 1/2+1/3,
    20% of 80, LCM/GCF, primes, averages, times tables, sqrt...
  * Teaches topics from its built-in knowledge base
  * GENERATES PLAYABLE HTML GAMES (quiz / clicker / memory / typing)
  * Learns new things and remembers them in matix_brain_memory.json
    - "remember the club meets on friday"
    - "teach: what is our club motto = math is power"
  * Speaks OpenAI format so the club app plugs straight in
=====================================================================
"""
import json, math, os, random, re, socket, sys, time, threading
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "1.0"
PORT = int(os.environ.get("MATIX_BRAIN_PORT", "8787"))
HERE = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(HERE, "matix_brain_memory.json")
BOOT_TIME = time.time()

# ---------------------------------------------------------------
# MEMORY - the brain remembers between restarts
# ---------------------------------------------------------------
_MEM_LOCK = threading.Lock()

def load_memory():
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            m = json.load(f)
            if isinstance(m, dict):
                m.setdefault("facts", [])
                m.setdefault("taught", {})
                m.setdefault("chats", 0)
                return m
    except Exception:
        pass
    return {"facts": [], "taught": {}, "chats": 0}

MEMORY = load_memory()

def save_memory():
    with _MEM_LOCK:
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(MEMORY, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

# ---------------------------------------------------------------
# TEXT HELPERS
# ---------------------------------------------------------------
def norm(t):
    return re.sub(r"\s+", " ", str(t or "").strip().lower())

def tokenize(t):
    return re.findall(r"[a-z0-9']+", norm(t))

def fmt_num(v):
    if isinstance(v, Fraction):
        if v.denominator == 1:
            return str(v.numerator)
        return "%s/%s" % (v.numerator, v.denominator)
    f = float(v)
    if abs(f - round(f)) < 1e-9 and abs(f) < 1e15:
        return str(int(round(f)))
    return ("%.6f" % f).rstrip("0").rstrip(".")

# ---------------------------------------------------------------
# MATH ENGINE - a real expression parser (no eval, fully safe)
# ---------------------------------------------------------------
class MathError(Exception):
    pass

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")

def _lex(expr):
    tokens, i = [], 0
    while i < len(expr):
        c = expr[i]
        if c.isspace():
            i += 1; continue
        if c.isdigit() or (c == "." and i + 1 < len(expr) and expr[i+1].isdigit()):
            m = _NUM_RE.match(expr, i)
            tokens.append(("num", float(m.group()))); i = m.end(); continue
        if c.isalpha():
            j = i
            while j < len(expr) and expr[j].isalpha():
                j += 1
            tokens.append(("name", expr[i:j].lower())); i = j; continue
        if c in "+-*/^%(),":
            tokens.append((c, c)); i += 1; continue
        if c in "\u00d7\u22c5\u00b7":
            tokens.append(("*", "*")); i += 1; continue
        if c in "\u00f7:":
            tokens.append(("/", "/")); i += 1; continue
        raise MathError("I don't understand the symbol %r yet." % c)
    # implicit multiplication: 2(3+1), (2)(3), 2pi
    out = []
    for t in tokens:
        if out and out[-1][0] in ("num", ")") and t[0] in ("num", "name", "("):
            out.append(("*", "*"))
        out.append(t)
    return out

def _call_fn(name, args):
    a = [float(x) for x in args]
    if name in ("sqrt", "root"):
        if a[0] < 0: raise MathError("square root of a negative needs imaginary numbers!")
        r = math.sqrt(a[0])
        return r
    if name == "abs": return abs(a[0])
    if name == "round": return round(a[0], int(a[1]) if len(a) > 1 else 0)
    if name == "sin": return math.sin(math.radians(a[0]))
    if name == "cos": return math.cos(math.radians(a[0]))
    if name == "tan": return math.tan(math.radians(a[0]))
    if name in ("log", "log10"): return math.log(a[0], a[1] if len(a) > 1 else 10.0)
    if name == "ln": return math.log(a[0])
    if name == "floor": return math.floor(a[0])
    if name == "ceil": return math.ceil(a[0])
    raise MathError("I don't know the function %r" % name)

def evaluate(expr, exact=False):
    tokens = _lex(expr)
    if not tokens:
        raise MathError("empty")
    pos = [0]
    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else (None, None)
    def take(kind=None):
        t = peek()
        if t[0] is None or (kind and t[0] != kind):
            raise MathError("that expression looks unfinished")
        pos[0] += 1
        return t
    def parse_expr():
        v = parse_term()
        while peek()[0] in ("+", "-"):
            op = take()[0]
            r = parse_term()
            v = v + r if op == "+" else v - r
        return v
    def parse_term():
        v = parse_unary()
        while peek()[0] in ("*", "/", "%"):
            op = take()[0]
            r = parse_unary()
            if op == "*": v = v * r
            elif op == "/":
                if float(r) == 0: raise MathError("dividing by zero is the one thing even I can't do!")
                v = (Fraction(v) / Fraction(r)) if (exact and _is_frac(v) and _is_frac(r)) else (float(v) / float(r))
            else:
                if float(r) == 0: raise MathError("modulo by zero!")
                v = float(v) % float(r)
        return v
    def parse_unary():
        k = peek()[0]
        if k == "-":
            take(); return -parse_unary()
        if k == "+":
            take(); return parse_unary()
        return parse_power()
    def parse_power():
        base = parse_atom()
        if peek()[0] == "^":
            take()
            expo = parse_unary()
            return float(base) ** float(expo)
        return base
    def parse_atom():
        k, v = peek()
        if k == "num":
            take()
            if exact and float(v).is_integer():
                return Fraction(int(v))
            return v
        if k == "name":
            take()
            if v == "pi": return math.pi
            if v == "e": return math.e
            if v == "x": raise MathError("algebra")
            if peek()[0] == "(":
                take("(")
                args = [parse_expr()]
                while peek()[0] == ",":
                    take(","); args.append(parse_expr())
                take(")")
                return _call_fn(v, args)
            raise MathError("I don't know what %r means in math" % v)
        if k == "(":
            take("(")
            v2 = parse_expr()
            take(")")
            return v2
        raise MathError("I got confused reading that expression")
    def _is_frac(x):
        return isinstance(x, Fraction) or (isinstance(x, float) and x.is_integer()) or isinstance(x, int)
    result = parse_expr()
    if pos[0] != len(tokens):
        raise MathError("there's a part I couldn't read")
    return result

# ----- equation solvers -----
def _parse_side(side):
    side = side.replace(" ", "").replace("*x", "x").replace("X", "x")
    if not side: raise MathError("empty side")
    if side[0] not in "+-": side = "+" + side
    coef, const = Fraction(0), Fraction(0)
    for piece in re.findall(r"[+-][^+-]*", side):
        sign = -1 if piece[0] == "-" else 1
        body = piece[1:]
        if not body: raise MathError("bad equation")
        if body.endswith("x"):
            num = body[:-1]
            c = Fraction(num) if num else Fraction(1)
            coef += sign * c
        else:
            const += sign * Fraction(body)
    return coef, const

def solve_linear(text):
    t = norm(text).replace("solve", "").replace("for x", "").replace("?", "").strip()
    if "=" not in t or "x" not in t: return None
    if "x^2" in t.replace(" ", "") or "x\u00b2" in t: return None
    try:
        left, right = t.split("=", 1)
        a1, b1 = _parse_side(left)
        a2, b2 = _parse_side(right)
    except Exception:
        return None
    a, b = a1 - a2, b2 - b1
    if a == 0:
        return "That equation has no x left after simplifying \u2014 " + ("every x works! \u267e\ufe0f" if b == 0 else "so there's no solution. \u274c")
    x = b / a
    steps = []
    steps.append("\U0001f9ee Let's solve it together:")
    steps.append("1\ufe0f\u20e3  Move everything: %sx = %s" % (fmt_num(a), fmt_num(b)))
    steps.append("2\ufe0f\u20e3  Divide both sides by %s" % fmt_num(a))
    extra = "" if x.denominator == 1 else "  (= %s as a decimal)" % fmt_num(float(x))
    steps.append("\u2705 x = %s%s" % (fmt_num(x), extra))
    return "\n".join(steps)

def solve_quadratic(text):
    t = norm(text).replace("solve", "").replace("?", "").replace("\u00b2", "^2").replace(" ", "")
    if "x^2" not in t: return None
    if "=" not in t: t += "=0"
    try:
        left, right = t.split("=", 1)
        rv = Fraction(right) if right else Fraction(0)
    except Exception:
        return None
    if left and left[0] not in "+-": left = "+" + left
    a = b = c = Fraction(0)
    try:
        for piece in re.findall(r"[+-][^+-]*", left):
            sign = -1 if piece[0] == "-" else 1
            body = piece[1:]
            if body.endswith("x^2"):
                num = body[:-3]
                a += sign * (Fraction(num) if num else Fraction(1))
            elif body.endswith("x"):
                num = body[:-1]
                b += sign * (Fraction(num) if num else Fraction(1))
            elif body:
                c += sign * Fraction(body)
    except Exception:
        return None
    c -= rv
    if a == 0: return None
    disc = b * b - 4 * a * c
    lines = ["\U0001f9ee Quadratic! a=%s, b=%s, c=%s" % (fmt_num(a), fmt_num(b), fmt_num(c)),
             "Discriminant: b\u00b2-4ac = %s" % fmt_num(disc)]
    if disc < 0:
        lines.append("\u274c The discriminant is negative \u2014 no real solutions (they're imaginary!)")
        return "\n".join(lines)
    sq = math.sqrt(float(disc))
    x1 = (-float(b) + sq) / (2 * float(a))
    x2 = (-float(b) - sq) / (2 * float(a))
    if abs(x1 - x2) < 1e-12:
        lines.append("\u2705 One solution: x = %s" % fmt_num(x1))
    else:
        lines.append("\u2705 Two solutions: x = %s  or  x = %s" % (fmt_num(x1), fmt_num(x2)))
    return "\n".join(lines)

# ----- more math skills -----
def do_percent(text):
    t = norm(text)
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)", t)
    if m:
        p, n = float(m.group(1)), float(m.group(2))
        return "\U0001f4af %s%% of %s = %s\n(How: %s \u00f7 100 \u00d7 %s)" % (fmt_num(p), fmt_num(n), fmt_num(p / 100 * n), fmt_num(p), fmt_num(n))
    m = re.search(r"what\s+percent(?:age)?\s+of\s+(\d+(?:\.\d+)?)\s+is\s+(\d+(?:\.\d+)?)", t)
    if m:
        whole, part = float(m.group(1)), float(m.group(2))
        if whole == 0: return "Can't take a percent of zero!"
        return "\U0001f4af %s is %s%% of %s" % (fmt_num(part), fmt_num(part / whole * 100), fmt_num(whole))
    m = re.search(r"(increase|decrease)\s+(\d+(?:\.\d+)?)\s+by\s+(\d+(?:\.\d+)?)\s*%", t)
    if m:
        base, p = float(m.group(2)), float(m.group(3))
        mult = 1 + p / 100 if m.group(1) == "increase" else 1 - p / 100
        return "\U0001f4af %s %sd by %s%% = %s" % (fmt_num(base), m.group(1), fmt_num(p), fmt_num(base * mult))
    return None

def do_gcf_lcm(text):
    t = norm(text)
    m = re.search(r"\b(gcf|gcd|hcf|lcm)\b", t)
    if not m: return None
    nums = [int(x) for x in re.findall(r"\d+", t)]
    nums = [n for n in nums if n > 0]
    if len(nums) < 2: return None
    kind = m.group(1)
    g = nums[0]
    for n in nums[1:]: g = math.gcd(g, n)
    if kind in ("gcf", "gcd", "hcf"):
        return "\U0001f9e9 GCF of %s = %s" % (", ".join(map(str, nums)), g)
    l = nums[0]
    for n in nums[1:]: l = l * n // math.gcd(l, n)
    return "\U0001f9e9 LCM of %s = %s" % (", ".join(map(str, nums)), l)

def is_prime(n):
    if n < 2: return False
    if n < 4: return True
    if n % 2 == 0: return False
    i = 3
    while i * i <= n:
        if n % i == 0: return False
        i += 2
    return True

def prime_factors(n):
    out, d = [], 2
    while d * d <= n:
        while n % d == 0:
            out.append(d); n //= d
        d += 1
    if n > 1: out.append(n)
    return out

def do_primes(text):
    t = norm(text)
    m = re.search(r"is\s+(\d+)\s+(?:a\s+)?prime", t)
    if m:
        n = int(m.group(1))
        if is_prime(n):
            return "\u2705 Yes! %d is prime \u2014 only 1 and %d divide it." % (n, n)
        if n >= 2:
            f = prime_factors(n)
            return "\u274c Nope, %d is not prime. It breaks into %s." % (n, " \u00d7 ".join(map(str, f)))
        return "\u274c %d is not prime (primes start at 2)." % n
    m = re.search(r"prime\s+factors?\s+of\s+(\d+)", t)
    if m:
        n = int(m.group(1))
        if n < 2: return "Pick a number 2 or bigger!"
        return "\U0001f9e9 %d = %s" % (n, " \u00d7 ".join(map(str, prime_factors(n))))
    m = re.search(r"factors?\s+of\s+(\d+)", t)
    if m:
        n = int(m.group(1))
        fs = [i for i in range(1, n + 1) if n % i == 0]
        return "\U0001f9e9 Factors of %d: %s" % (n, ", ".join(map(str, fs)))
    return None

def do_timestable(text):
    m = re.search(r"(?:times\s*table|multiplication\s*table|table)\s*(?:of|for)?\s*(\d+)", norm(text))
    if not m: return None
    n = int(m.group(1))
    rows = ["%d \u00d7 %d = %d" % (n, i, n * i) for i in range(1, 13)]
    return "\U0001f4da The %d times table:\n" % n + "\n".join(rows)

def do_average(text):
    t = norm(text)
    if not re.search(r"\b(average|mean)\b", t): return None
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", t)]
    if len(nums) < 2: return None
    avg = sum(nums) / len(nums)
    return "\U0001f4ca Average of %s = (%s) \u00f7 %d = %s" % (
        ", ".join(fmt_num(n) for n in nums),
        " + ".join(fmt_num(n) for n in nums),
        len(nums), fmt_num(avg))

def do_calc(text):
    t = norm(text)
    for w in ("what is", "what's", "whats", "calculate", "calc", "compute", "how much is", "solve", "=", "?"):
        t = t.replace(w, " ")
    t = t.replace("x\u00b2", "x^2").replace("\u00b2", "^2").replace("plus", "+").replace("minus", "-").replace("times", "*").replace("divided by", "/").strip()
    if not re.search(r"\d", t): return None
    if not re.fullmatch(r"[0-9\s\.\+\-\*/\^%\(\),a-z\u00d7\u00f7\u22c5\u00b7:]+", t): return None
    words = re.findall(r"[a-z]+", t)
    allowed = {"sqrt", "root", "abs", "round", "sin", "cos", "tan", "log", "ln", "pi", "e", "floor", "ceil"}
    if any(w not in allowed for w in words): return None
    if not (re.search(r"[\+\-\*/\^%\u00d7\u00f7]", t) or words): return None
    exact = bool(re.fullmatch(r"[0-9\s/\+\-\*\(\)]+", t)) and "/" in t
    try:
        v = evaluate(t, exact=exact)
    except MathError as e:
        if str(e) == "algebra": return None
        return None
    except Exception:
        return None
    if isinstance(v, Fraction) and v.denominator != 1:
        dec = fmt_num(float(v))
        mixed = ""
        if abs(v.numerator) > v.denominator:
            whole = v.numerator // v.denominator if v.numerator > 0 else -((-v.numerator) // v.denominator)
            rem = abs(v.numerator) - abs(whole) * v.denominator
            mixed = "  (= %d %d/%d)" % (whole, rem, v.denominator)
        return "\U0001f9ee = %s%s  \u2248 %s" % (fmt_num(v), mixed, dec)
    return "\U0001f9ee = %s" % fmt_num(v)

def do_sqrt_words(text):
    m = re.search(r"square\s+root\s+of\s+(\d+(?:\.\d+)?)", norm(text))
    if not m: return None
    n = float(m.group(1))
    r = math.sqrt(n)
    perfect = " \u2014 a perfect square!" if float(int(r + 0.5)) ** 2 == n else ""
    return "\U0001f9ee \u221a%s = %s%s" % (fmt_num(n), fmt_num(r), perfect)

def try_math(text):
    for fn in (solve_quadratic, solve_linear, do_percent, do_gcf_lcm, do_primes,
               do_timestable, do_average, do_sqrt_words, do_calc):
        try:
            r = fn(text)
        except Exception:
            r = None
        if r: return r
    return None

# ---------------------------------------------------------------
# KNOWLEDGE BASE - what the brain knows (add your own topics!)
# ---------------------------------------------------------------
KB = {
 "matix": {"emoji": "\u2b50", "what": "Matix the Math Club is OUR club, founded by Ghadi.",
  "facts": ["The club has its own app with games, points, chat, AI and more.",
            "Members include ghadi, dahlia, yara, jad, marwan, mak and hicham.",
            "The club motto: math is power!",
            "This AI brain was built BY the club, in Python, with zero APIs."]},
 "minecraft": {"emoji": "\u26cf\ufe0f", "what": "Minecraft is a sandbox game about mining blocks and building anything.",
  "facts": ["You punch trees for wood, craft tools, then mine stone, iron and diamonds.",
            "At night monsters spawn: zombies, skeletons, spiders and creepers (they explode!).",
            "The Ender Dragon is the final boss, living in a dimension called The End.",
            "Redstone works like electricity, so you can build real logic machines.",
            "There is no single way to win: you build, explore, survive and create."]},
 "roblox": {"emoji": "\U0001f3ae", "what": "Roblox is a platform full of games made by players themselves.",
  "facts": ["Games on Roblox are made with a language called Luau (like Lua).",
            "Popular games include obbys (obstacle courses), tycoons and simulators.",
            "Robux is the in-game money used for avatars and passes."]},
 "chess": {"emoji": "\u265f\ufe0f", "what": "Chess is a 2-player strategy game on an 8x8 board.",
  "facts": ["Each side starts with 16 pieces; the goal is to checkmate the king.",
            "The queen is the strongest piece: it moves like a rook and bishop combined.",
            "Knights move in an L shape and can jump over pieces.",
            "There are more possible chess games than atoms in the observable universe."]},
 "football": {"emoji": "\u26bd", "what": "Football (soccer) is the world's most popular sport.",
  "facts": ["Two teams of 11 try to score goals in 90 minutes.",
            "The World Cup happens every 4 years and billions watch it.",
            "Only the goalkeeper can use hands, and only inside the penalty box."]},
 "basketball": {"emoji": "\U0001f3c0", "what": "Basketball is a 5v5 sport about shooting a ball through a hoop.",
  "facts": ["A normal basket is 2 points, behind the arc is 3, free throws are 1.",
            "The hoop is 3.05 meters (10 feet) high.",
            "The NBA is the most famous league in the world."]},
 "space": {"emoji": "\U0001f680", "what": "Space is everything beyond Earth's atmosphere.",
  "facts": ["Space is silent because there is no air to carry sound.",
            "The nearest star after the Sun is over 4 light-years away.",
            "Astronauts float because they are in constant free-fall around Earth."]},
 "sun": {"emoji": "\u2600\ufe0f", "what": "The Sun is the star at the center of our solar system.",
  "facts": ["About 1.3 million Earths could fit inside the Sun.",
            "Sunlight takes about 8 minutes and 20 seconds to reach Earth.",
            "The Sun is about 4.6 billion years old, roughly halfway through its life."]},
 "moon": {"emoji": "\U0001f319", "what": "The Moon is Earth's only natural satellite.",
  "facts": ["The Moon causes the ocean tides with its gravity.",
            "12 people have walked on the Moon, the first in 1969.",
            "The same side of the Moon always faces Earth."]},
 "mars": {"emoji": "\U0001f534", "what": "Mars is the fourth planet, known as the Red Planet.",
  "facts": ["Mars is red because of rusty iron dust on its surface.",
            "It has the tallest volcano in the solar system: Olympus Mons.",
            "Robot rovers like Curiosity and Perseverance explore it right now."]},
 "black holes": {"emoji": "\u26ab", "what": "A black hole is a place where gravity is so strong nothing escapes.",
  "facts": ["Not even light can escape, which is why it looks black.",
            "They form when giant stars collapse at the end of their lives.",
            "Time actually runs slower near a black hole \u2014 real physics!"]},
 "dinosaurs": {"emoji": "\U0001f996", "what": "Dinosaurs ruled Earth for about 165 million years.",
  "facts": ["They went extinct 66 million years ago, likely from an asteroid impact.",
            "Birds are living dinosaurs \u2014 they evolved from small feathered ones.",
            "T. rex had banana-sized teeth and a bite stronger than any land animal today."]},
 "volcanoes": {"emoji": "\U0001f30b", "what": "Volcanoes are openings where melted rock erupts from inside Earth.",
  "facts": ["Lava can reach about 1,200 degrees Celsius.",
            "Most volcanoes sit along the Pacific 'Ring of Fire'.",
            "Volcanic ash makes soil super fertile for farming."]},
 "oceans": {"emoji": "\U0001f30a", "what": "Oceans cover about 71% of Earth's surface.",
  "facts": ["We have explored less than 20% of the ocean.",
            "The deepest point, the Mariana Trench, is about 11 km down.",
            "The ocean makes over half of the oxygen we breathe."]},
 "sharks": {"emoji": "\U0001f988", "what": "Sharks are ancient fish with skeletons made of cartilage.",
  "facts": ["Sharks existed before trees \u2014 over 400 million years.",
            "They keep growing new teeth their whole lives.",
            "Most sharks are harmless to humans."]},
 "dogs": {"emoji": "\U0001f436", "what": "Dogs were the first animal humans ever tamed.",
  "facts": ["A dog's sense of smell is up to 100,000 times better than ours.",
            "Dogs understand human pointing better than chimpanzees do.",
            "A wagging tail can mean excitement, not always happiness."]},
 "cats": {"emoji": "\U0001f431", "what": "Cats are small hunters that adopted humans about 9,000 years ago.",
  "facts": ["Cats purr at a frequency that may help heal bones.",
            "They sleep 12-16 hours a day.",
            "A group of cats is called a clowder."]},
 "pandas": {"emoji": "\U0001f43c", "what": "Giant pandas are bears that eat almost only bamboo.",
  "facts": ["They eat up to 38 kg of bamboo a day.",
            "Newborn pandas are about the size of a stick of butter.",
            "They live mainly in mountain forests of China."]},
 "bees": {"emoji": "\U0001f41d", "what": "Bees are pollinators that make a third of our food possible.",
  "facts": ["A bee visits about 1,000 flowers a day.",
            "They dance (the waggle dance) to tell others where flowers are.",
            "Honey never spoils \u2014 sealed jars from ancient Egypt are still edible."]},
 "lebanon": {"emoji": "\U0001f1f1\U0001f1e7", "what": "Lebanon is a beautiful country on the Mediterranean Sea.",
  "facts": ["Its capital is Beirut, one of the oldest cities in the world.",
            "The cedar tree on its flag has been its symbol for thousands of years.",
            "You can ski in the mountains and swim in the sea on the same day."]},
 "beirut": {"emoji": "\U0001f307", "what": "Beirut is the capital of Lebanon.",
  "facts": ["People have lived there for over 5,000 years.",
            "It sits right on the Mediterranean coast.",
            "It's famous for food, music and history all mixed together."]},
 "france": {"emoji": "\U0001f1eb\U0001f1f7", "what": "France is a country in western Europe.",
  "facts": ["Paris, its capital, has the Eiffel Tower (330 m tall).",
            "French is spoken by about 300 million people worldwide.",
            "France invented the metric system during the French Revolution."]},
 "japan": {"emoji": "\U0001f1ef\U0001f1f5", "what": "Japan is an island country in East Asia.",
  "facts": ["It has bullet trains that go over 300 km/h.",
            "Tokyo is the biggest city in the world by metro population.",
            "Japan invented anime, Nintendo and instant noodles."]},
 "egypt": {"emoji": "\U0001f1ea\U0001f1ec", "what": "Egypt is home to one of the oldest civilizations ever.",
  "facts": ["The pyramids of Giza are over 4,500 years old.",
            "Ancient Egyptians used math and geometry to build them precisely.",
            "The Nile is the longest river in Africa."]},
 "pyramids": {"emoji": "\U0001f53a", "what": "The pyramids were giant tombs for Egyptian pharaohs.",
  "facts": ["The Great Pyramid was the tallest building on Earth for 3,800 years.",
            "It contains about 2.3 million stone blocks.",
            "Its base is level to within just a few centimeters \u2014 ancient math power!"]},
 "computers": {"emoji": "\U0001f4bb", "what": "Computers are machines that follow instructions (code) super fast.",
  "facts": ["Everything inside a computer is 1s and 0s \u2014 binary math.",
            "The first programmer was Ada Lovelace, in the 1840s!",
            "A modern phone is millions of times faster than the Apollo moon computer."]},
 "internet": {"emoji": "\U0001f310", "what": "The internet is billions of computers talking to each other.",
  "facts": ["Data travels through giant cables under the oceans.",
            "The web was invented in 1989 by Tim Berners-Lee.",
            "About 5 billion people use the internet today."]},
 "python": {"emoji": "\U0001f40d", "what": "Python is a friendly programming language \u2014 this brain is written in it!",
  "facts": ["It's named after Monty Python, not the snake.",
            "Python reads almost like English: print('hello').",
            "NASA, YouTube and this very Matix Brain all use Python."]},
 "ai": {"emoji": "\U0001f9e0", "what": "AI means making computers do things that seem smart.",
  "facts": ["Big AIs learn patterns from huge amounts of examples, not from rules.",
            "What makes them smart is TRAINING on data, not how many lines of code.",
            "This brain uses a small neural network trained fresh every time it starts."]},
 "robots": {"emoji": "\U0001f916", "what": "Robots are machines that sense, think and act.",
  "facts": ["The word robot comes from a Czech word meaning 'forced work'.",
            "Robots build most cars today.",
            "Some robots explore places too dangerous for humans, like Mars."]},
 "electricity": {"emoji": "\u26a1", "what": "Electricity is the flow of tiny particles called electrons.",
  "facts": ["Lightning is a giant electric spark hotter than the Sun's surface.",
            "It moves through wires near the speed of light.",
            "Batteries push electrons using chemistry."]},
 "gravity": {"emoji": "\U0001f30d", "what": "Gravity is the force that pulls masses together.",
  "facts": ["It keeps the Moon around Earth and Earth around the Sun.",
            "On the Moon you'd weigh 6 times less.",
            "Einstein showed gravity is really bending of space and time."]},
 "light": {"emoji": "\U0001f4a1", "what": "Light is energy we can see, traveling in waves.",
  "facts": ["Light speed is 299,792 km per second \u2014 the universe's speed limit.",
            "White light is all rainbow colors mixed together.",
            "Mirrors flip left-right because they bounce light straight back."]},
 "sound": {"emoji": "\U0001f50a", "what": "Sound is vibration traveling through air, water or solids.",
  "facts": ["Sound can't travel in space \u2014 no air, no sound.",
            "Sound travels about 343 m/s in air, way slower than light.",
            "That's why you see lightning before hearing thunder."]},
 "rainbows": {"emoji": "\U0001f308", "what": "Rainbows appear when sunlight bends through raindrops.",
  "facts": ["Each raindrop acts like a tiny prism splitting light into colors.",
            "A rainbow is actually a full circle \u2014 the ground cuts it in half.",
            "No two people see exactly the same rainbow."]},
 "water cycle": {"emoji": "\U0001f4a7", "what": "The water cycle moves water between sea, sky and land forever.",
  "facts": ["Evaporation: sun turns water into vapor that rises.",
            "Condensation: vapor cools into clouds.",
            "Precipitation: rain or snow falls, flows back to the sea, repeat!"]},
 "photosynthesis": {"emoji": "\U0001f331", "what": "Photosynthesis is how plants make food from sunlight.",
  "facts": ["Plants take in CO2 and water, and use light to make sugar.",
            "Oxygen is the 'waste' they release \u2014 lucky for us!",
            "Chlorophyll makes leaves green and captures the light."]},
 "human body": {"emoji": "\U0001fac0", "what": "Your body is trillions of cells working together.",
  "facts": ["Your heart beats about 100,000 times a day.",
            "Bones are stronger than steel for their weight.",
            "Your body makes 25 million new cells every second."]},
 "brain": {"emoji": "\U0001f9e0", "what": "The brain is the most complex thing we know of.",
  "facts": ["It has about 86 billion neurons with trillions of connections.",
            "It uses about 20% of your energy while being 2% of your weight.",
            "Learning literally rewires it \u2014 practice makes real changes."]},
 "planets": {"emoji": "\U0001fa90", "what": "Our solar system has 8 planets orbiting the Sun.",
  "facts": ["Order: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune.",
            "Jupiter is so big all other planets could fit inside it.",
            "Venus is hotter than Mercury because of its thick atmosphere."]},
 "pi": {"emoji": "\U0001f967", "what": "Pi is the ratio of a circle's circumference to its diameter.",
  "facts": ["Pi is about 3.14159 and its digits never end or repeat.",
            "Pi Day is March 14 (3/14) \u2014 people eat pie!",
            "Computers have calculated over 100 trillion digits of pi."]},
 "zero": {"emoji": "0\ufe0f\u20e3", "what": "Zero is the number that changed math forever.",
  "facts": ["Ancient Romans had no symbol for zero at all.",
            "Zero as a real number was developed in India around 1,500 years ago.",
            "Without zero there would be no computers \u2014 binary needs 0 and 1."]},
 "fibonacci": {"emoji": "\U0001f41a", "what": "The Fibonacci sequence adds the two previous numbers: 1,1,2,3,5,8...",
  "facts": ["Sunflower seeds and pinecones grow in Fibonacci spirals.",
            "Dividing neighbors approaches the golden ratio 1.618.",
            "It appears in art, music, nature and even galaxies."]},
 "fractions": {"emoji": "\U0001f355", "what": "A fraction is a part of a whole, like a pizza slice.",
  "facts": ["The top is the numerator (how many parts), bottom is the denominator (how many total).",
            "To add fractions you need the same denominator.",
            "Every fraction is also a division: 3/4 = 3 divided by 4 = 0.75."]},
 "decimals": {"emoji": "\U0001f522", "what": "Decimals show parts of a whole using place value after the point.",
  "facts": ["0.5 means 5 tenths, which is the same as 1/2.",
            "Money uses decimals: $2.75 is 2 wholes and 75 hundredths.",
            "Multiplying by 10 just slides the decimal point right."]},
 "percentages": {"emoji": "\U0001f4af", "what": "Percent means 'out of 100'.",
  "facts": ["50% = half, 25% = a quarter, 100% = the whole thing.",
            "To find 10%, just divide by 10 \u2014 then build from there.",
            "Shops use percentages for every discount you've ever seen."]},
 "algebra": {"emoji": "\u2696\ufe0f", "what": "Algebra uses letters to stand for unknown numbers.",
  "facts": ["An equation is a balance: do the same to both sides and it stays true.",
            "The word algebra comes from Arabic: al-jabr.",
            "Solving for x is just carefully undoing operations in reverse."]},
 "geometry": {"emoji": "\U0001f4d0", "what": "Geometry is the math of shapes, sizes and space.",
  "facts": ["Triangle angles always add up to 180 degrees.",
            "A circle's area is pi times radius squared.",
            "The Egyptians used geometry to rebuild fields after Nile floods."]},
 "primes": {"emoji": "\U0001f511", "what": "Primes are numbers only divisible by 1 and themselves.",
  "facts": ["2 is the only even prime.",
            "There are infinitely many primes \u2014 proved 2,300 years ago by Euclid.",
            "Internet security is built on giant prime numbers."]},
 "probability": {"emoji": "\U0001f3b2", "what": "Probability measures how likely something is, from 0 to 1.",
  "facts": ["A coin flip is 1/2, rolling a six is 1/6.",
            "Casinos always win long-term because of probability math.",
            "Weather forecasts like '70% rain' are probability in action."]},
 "negative numbers": {"emoji": "\u2744\ufe0f", "what": "Negative numbers are numbers below zero.",
  "facts": ["Temperature uses them all the time: -5\u00b0C is 5 below freezing.",
            "Subtracting a negative is the same as adding: 5-(-3)=8.",
            "They were once called 'absurd numbers' before people accepted them."]},
 "angles": {"emoji": "\U0001f4d0", "what": "An angle measures the turn between two lines.",
  "facts": ["A right angle is 90\u00b0, a straight line is 180\u00b0, a full turn is 360\u00b0.",
            "Less than 90\u00b0 is acute, more is obtuse.",
            "Skaters say '360' because of angle math!"]},
 "triangles": {"emoji": "\U0001f53a", "what": "Triangles are the strongest shape in engineering.",
  "facts": ["Bridges and towers are full of triangles for strength.",
            "Pythagoras: a\u00b2+b\u00b2=c\u00b2 for right triangles.",
            "Any triangle's angles sum to exactly 180\u00b0."]},
 "circles": {"emoji": "\u2b55", "what": "A circle is every point at the same distance from a center.",
  "facts": ["Circumference = 2\u00d7pi\u00d7radius, Area = pi\u00d7radius\u00b2.",
            "Wheels work because a circle rolls perfectly smoothly.",
            "A circle has infinite lines of symmetry."]},
 "multiplication": {"emoji": "\u2716\ufe0f", "what": "Multiplication is repeated addition, done fast.",
  "facts": ["3\u00d74 means 3 groups of 4.",
            "Order doesn't matter: 6\u00d77 = 7\u00d76 (commutative!).",
            "Anything times zero is zero."]},
 "division": {"emoji": "\u2797", "what": "Division splits a number into equal groups.",
  "facts": ["12\u00f73 asks: how many 3s fit in 12? Four!",
            "Division is the reverse of multiplication.",
            "You can never divide by zero \u2014 it breaks math."]},
}

JOKES = [
 "Why was 6 afraid of 7? Because 7 8 9! \U0001f602",
 "Parallel lines have so much in common... it's a shame they'll never meet. \U0001f625",
 "Why did the student do multiplication on the floor? The teacher said not to use tables! \U0001f605",
 "What do you call friends who love math? Alge-BROS. \U0001f60e",
 "Why is the obtuse angle always upset? Because it's never right. \U0001f4d0",
 "I saw my math teacher with graph paper. I think they're plotting something. \U0001f440",
 "Why did the computer go to the doctor? It caught a virus! \U0001f912",
 "What's a math teacher's favorite season? SUM-mer! \u2600\ufe0f",
 "Why do plants hate math? It gives them square roots. \U0001f331",
 "What did zero say to eight? Nice belt! \U0001f602",
 "Why was the equal sign so humble? It knew it wasn't less than or greater than anyone. \U0001f91d",
 "How do you make seven even? Take away the S! \U0001f92f",
]

GREETS = [
 "Hey {name}! \U0001f44b Matix Brain online \u2014 ask me math, facts, or say 'make a game'!",
 "Hello hello! \U0001f9e0 Your club's own AI is listening. What shall we solve?",
 "Hi {name}! Ready when you are \u2014 equations, topics, jokes, games... bring it!",
 "Yo! \u2b50 Matix Brain here, 100% made-by-the-club. What do you need?",
]

ENCOURAGE = [
 "Keep going \u2014 every mistake is your brain leveling up! \U0001f4aa",
 "You've got this. Small steps beat big worries. \u2b50",
 "Math is power \u2014 and you're getting stronger! \U0001f9e0",
]

FALLBACKS = [
 "Hmm, I'm not sure about that one yet! \U0001f914 Try asking me math (like '3x+5=20'), a topic ('tell me about volcanoes'), or say 'make a quiz game'. You can also TEACH me: teach: your question = the answer",
 "That one's outside my brain for now! \U0001f605 I'm great at math, topics like {topic}, jokes and games. And if you teach me ('teach: q = a'), I'll remember forever!",
 "I don't know that YET \u2014 but I learn! Say: teach: <question> = <answer>. Meanwhile, want a math challenge or a game? \U0001f3ae",
]

# ---------------------------------------------------------------
# INTENT ENGINE - naive bayes + tiny neural net (trained at boot)
# ---------------------------------------------------------------
INTENT_DATA = [
 ("greet", "hi"), ("greet", "hello"), ("greet", "hey there"), ("greet", "yo"), ("greet", "good morning"),
 ("greet", "good evening"), ("greet", "hola"), ("greet", "whats up"), ("greet", "hey brain"), ("greet", "marhaba"),
 ("bye", "bye"), ("bye", "goodbye"), ("bye", "see you later"), ("bye", "good night"), ("bye", "im leaving now"),
 ("thanks", "thanks"), ("thanks", "thank you so much"), ("thanks", "thx"), ("thanks", "ty brain"), ("thanks", "shukran"),
 ("whoami", "who are you"), ("whoami", "what are you"), ("whoami", "are you chatgpt"), ("whoami", "are you real ai"),
 ("whoami", "who made you"), ("whoami", "what is your name"), ("whoami", "introduce yourself"),
 ("joke", "tell me a joke"), ("joke", "joke"), ("joke", "make me laugh"), ("joke", "another joke"), ("joke", "say something funny"),
 ("help", "help"), ("help", "what can you do"), ("help", "commands"), ("help", "how do i use you"), ("help", "what do you know"),
 ("mood_good", "im happy today"), ("mood_good", "i feel great"), ("mood_good", "today was awesome"),
 ("mood_bad", "im sad"), ("mood_bad", "i feel bad"), ("mood_bad", "i failed my test"), ("mood_bad", "im tired"),
 ("mood_bad", "i had a bad day"), ("mood_bad", "math is too hard for me"),
 ("praise", "you are smart"), ("praise", "good job"), ("praise", "you are the best"), ("praise", "amazing answer"),
 ("insult", "you are dumb"), ("insult", "you are stupid"), ("insult", "you suck"), ("insult", "useless bot"),
 ("love", "i love you"), ("love", "do you love me"),
 ("game", "make a game"), ("game", "create a quiz game"), ("game", "build me a clicker game"),
 ("game", "generate a memory game"), ("game", "make a typing game"), ("game", "i want a new game"),
 ("game", "make a math quiz"), ("game", "create a game about space"),
 ("topic", "tell me about minecraft"), ("topic", "what is a black hole"), ("topic", "teach me fractions"),
 ("topic", "explain gravity"), ("topic", "what are primes"), ("topic", "tell me about lebanon"),
 ("topic", "facts about sharks"), ("topic", "what is photosynthesis"), ("topic", "learn about space"),
 ("remember", "remember that the club meets friday"), ("remember", "remember my favorite number is 7"),
 ("remember", "dont forget the tournament is saturday"),
 ("recall", "what do you remember"), ("recall", "show your memory"), ("recall", "what did i tell you to remember"),
 ("teach", "teach: what is our motto = math is power"), ("teach", "learn this answer"),
 ("time", "what time is it"), ("time", "what day is today"), ("time", "whats the date"),
 ("owner", "who is the owner"), ("owner", "who is ghadi"), ("owner", "who runs the club"),
 ("encourage", "motivate me"), ("encourage", "i need motivation"), ("encourage", "encourage me please"),
]

class NaiveBayes:
    def __init__(self):
        self.word_counts = {}
        self.intent_totals = {}
        self.vocab = set()
    def train(self, data):
        for intent, text in data:
            self.intent_totals[intent] = self.intent_totals.get(intent, 0) + 1
            wc = self.word_counts.setdefault(intent, {})
            for w in tokenize(text):
                wc[w] = wc.get(w, 0) + 1
                self.vocab.add(w)
    def predict(self, text):
        words = tokenize(text)
        if not words: return (None, 0.0)
        total_docs = sum(self.intent_totals.values())
        best, best_lp, scores = None, None, {}
        for intent, count in self.intent_totals.items():
            lp = math.log(count / total_docs)
            wc = self.word_counts[intent]
            denom = sum(wc.values()) + len(self.vocab)
            for w in words:
                lp += math.log((wc.get(w, 0) + 1) / denom)
            scores[intent] = lp
            if best_lp is None or lp > best_lp:
                best, best_lp = intent, lp
        # softmax-ish confidence
        mx = max(scores.values())
        exps = {k: math.exp(v - mx) for k, v in scores.items()}
        s = sum(exps.values())
        return (best, exps[best] / s)

def _hashvec(text, dim=64):
    v = [0.0] * dim
    for w in tokenize(text):
        v[hash(w) % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]

class TinyNet:
    """A real neural network: 64 inputs -> 20 tanh -> softmax. Pure Python backprop."""
    def __init__(self, dim, hidden, out):
        rnd = random.Random(7)
        self.w1 = [[rnd.uniform(-0.5, 0.5) for _ in range(dim)] for _ in range(hidden)]
        self.b1 = [0.0] * hidden
        self.w2 = [[rnd.uniform(-0.5, 0.5) for _ in range(hidden)] for _ in range(out)]
        self.b2 = [0.0] * out
    def forward(self, x):
        h = [math.tanh(sum(w * xi for w, xi in zip(row, x)) + b) for row, b in zip(self.w1, self.b1)]
        o = [sum(w * hi for w, hi in zip(row, h)) + b for row, b in zip(self.w2, self.b2)]
        m = max(o)
        ex = [math.exp(v - m) for v in o]
        s = sum(ex)
        return h, [v / s for v in ex]
    def train(self, xs, ys, epochs=50, lr=0.15):
        for _ in range(epochs):
            for x, y in zip(xs, ys):
                h, p = self.forward(x)
                do = [pi - (1.0 if i == y else 0.0) for i, pi in enumerate(p)]
                for i in range(len(self.w2)):
                    row = self.w2[i]
                    for j in range(len(h)):
                        row[j] -= lr * do[i] * h[j]
                    self.b2[i] -= lr * do[i]
                dh = [(1 - h[j] * h[j]) * sum(self.w2[i][j] * do[i] for i in range(len(do))) for j in range(len(h))]
                for j in range(len(self.w1)):
                    roww = self.w1[j]
                    for k in range(len(x)):
                        if x[k]:
                            roww[k] -= lr * dh[j] * x[k]
                    self.b1[j] -= lr * dh[j]
    def predict(self, text, labels):
        _, p = self.forward(_hashvec(text))
        bi = max(range(len(p)), key=lambda i: p[i])
        return labels[bi], p[bi]

NB = NaiveBayes()
NB.train(INTENT_DATA)
_LABELS = sorted(set(i for i, _ in INTENT_DATA))
_NET = TinyNet(64, 20, len(_LABELS))
_NET.train([_hashvec(t) for _, t in INTENT_DATA], [_LABELS.index(i) for i, _ in INTENT_DATA])

def intent_of(text):
    nb_i, nb_c = NB.predict(text)
    nn_i, nn_c = _NET.predict(text, _LABELS)
    if nb_i == nn_i:
        return nb_i, max(nb_c, nn_c)
    if nb_c >= 0.55: return nb_i, nb_c
    if nn_c >= 0.75: return nn_i, nn_c
    return nb_i, nb_c * 0.6

# ---------------------------------------------------------------
# KNOWLEDGE LOOKUP + MEMORY COMMANDS
# ---------------------------------------------------------------
def kb_find(text):
    t = " " + norm(text) + " "
    best = None
    for key in sorted(KB.keys(), key=len, reverse=True):
        forms = [key, key.rstrip("s"), key + "s"]
        for f in set(forms):
            if " " + f + " " in t:
                if best is None or len(key) > len(best):
                    best = key
                break
    return (best, KB[best]) if best else (None, None)

def topic_reply(key, entry):
    facts = list(entry["facts"])
    random.shuffle(facts)
    picked = facts[:3]
    lines = ["%s %s" % (entry["emoji"], entry["what"]), ""]
    for f in picked:
        lines.append("\u2022 " + f)
    lines.append("")
    lines.append("Want more? Ask another question, or say 'make a quiz game about %s'! \U0001f3ae" % key)
    return "\n".join(lines)

def taught_lookup(text):
    tn = norm(text).rstrip("?!. ")
    taught = MEMORY.get("taught", {})
    if tn in taught: return taught[tn]
    tw = set(tokenize(tn))
    if not tw: return None
    best, bs = None, 0.0
    for q, a in taught.items():
        qw = set(tokenize(q))
        if not qw: continue
        j = len(tw & qw) / float(len(tw | qw))
        if j > bs: bs, best = j, a
    return best if bs >= 0.6 else None

def handle_memory_cmd(text, user):
    m = re.match(r"^\s*teach\s*:\s*(.+?)\s*=\s*(.+?)\s*$", text, re.I | re.S)
    if m:
        q, a = m.group(1).strip(), m.group(2).strip()
        MEMORY.setdefault("taught", {})[norm(q).rstrip("?!. ")] = a
        save_memory()
        return "\U0001f9e0 Learned it! Ask me '%s' anytime and I'll answer. (I remember even after restarting!)" % q
    m = re.match(r"^\s*(?:remember|don'?t forget)\s+(?:that\s+)?(.+?)\s*$", text, re.I | re.S)
    if m:
        fact = m.group(1).strip()
        MEMORY.setdefault("facts", []).append({"text": fact, "by": user or "someone", "t": int(time.time())})
        if len(MEMORY["facts"]) > 200: MEMORY["facts"] = MEMORY["facts"][-200:]
        save_memory()
        return "\U0001f4dd Saved to club memory: \u201c%s\u201d" % fact
    if re.search(r"what do you remember|show (your |the )?memory|club memory", text, re.I):
        facts = MEMORY.get("facts", [])
        taught = MEMORY.get("taught", {})
        if not facts and not taught:
            return "My club memory is empty so far! Say 'remember ...' or 'teach: question = answer' to fill it. \U0001f4dd"
        lines = ["\U0001f4dd Club memory:"]
        for f in facts[-10:]:
            lines.append("\u2022 %s (from %s)" % (f["text"], f.get("by", "?")))
        if taught:
            lines.append("\U0001f9e0 Things you taught me: %d" % len(taught))
        return "\n".join(lines)
    if re.match(r"^\s*forget everything\s*$", text, re.I):
        MEMORY["facts"], MEMORY["taught"] = [], {}
        save_memory()
        return "\U0001f4a8 Done \u2014 memory wiped clean."
    return None

MEMBERS = {
 "ghadi": "\U0001f451 Ghadi is the OWNER and founder of Matix the Math Club \u2014 and the reason I exist!",
 "dahlia": "\u2b50 Dahlia is a member of Matix the Math Club!",
 "yara": "\u2b50 Yara is a member of Matix the Math Club!",
 "jad": "\u2b50 Jad is a member of Matix the Math Club!",
 "marwan": "\u2b50 Marwan is a member of Matix the Math Club!",
 "mak": "\u2b50 Mak is a member of Matix the Math Club!",
 "hicham": "\u2b50 Hicham is a member of Matix the Math Club!",
}

# ---------------------------------------------------------------
# GAME GENERATOR - real playable HTML games, made by Python
# ---------------------------------------------------------------
THEMES = {
 "red": ("#ef4444", "#1a0b0b"), "blue": ("#3b82f6", "#0b0f1a"), "green": ("#22c55e", "#0b1a0f"),
 "purple": ("#a855f7", "#140b1a"), "pink": ("#ec4899", "#1a0b14"), "orange": ("#f97316", "#1a120b"),
 "gold": ("#eab308", "#1a160b"), "space": ("#818cf8", "#05060f"), "minecraft": ("#22c55e", "#0e1a0b"),
}

def pick_theme(prompt):
    p = norm(prompt)
    for k, v in THEMES.items():
        if k in p: return v
    return ("#7c3aed", "#0b0f1a")

GAME_SHELL = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><style>
*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
body{background:__BG__;color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:18px;text-align:center}
h1{font-size:1.5rem;margin:8px 0 2px}.sub{opacity:.7;font-size:.85rem;margin-bottom:14px}
.card{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:16px;padding:18px;max-width:520px;width:100%}
button{cursor:pointer;border:0;border-radius:12px;padding:12px 16px;font-size:1rem;font-weight:700;color:#fff;background:__ACCENT__;margin:6px;transition:transform .1s}
button:active{transform:scale(.95)}.stat{display:flex;justify-content:space-around;margin:10px 0;font-weight:700}
.big{font-size:2.2rem;margin:10px 0}.badge{background:__ACCENT__;border-radius:999px;padding:2px 12px;font-size:.8rem}
input{width:100%;padding:12px;border-radius:12px;border:2px solid __ACCENT__;background:rgba(0,0,0,.4);color:#fff;font-size:1.1rem;text-align:center;outline:none}
#arena{position:relative;height:320px;background:rgba(0,0,0,.3);border-radius:16px;overflow:hidden;margin-top:10px}
#target{position:absolute;font-size:2.6rem;cursor:pointer;user-select:none;transition:all .12s}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px}
.tile{aspect-ratio:1;display:flex;align-items:center;justify-content:center;font-size:1.9rem;background:rgba(255,255,255,.08);border-radius:12px;cursor:pointer;border:2px solid transparent}
.tile.open{background:__ACCENT__33;border-color:__ACCENT__}.tile.done{opacity:.35;pointer-events:none}
.choice{display:block;width:100%;text-align:left;background:rgba(255,255,255,.08);margin:6px 0}
.choice.right{background:#16a34a}.choice.wrong{background:#dc2626}
</style></head><body>
<h1>__EMOJI__ __TITLE__</h1><div class="sub">Made by Matix Brain \U0001f9e0 \u2014 100% Python-generated \u2022 Matix the Math Club</div>
<div class="card" id="game"></div>
<script>
__GAMEJS__
</script></body></html>"""

QUIZ_JS = """var QS=__QUESTIONS__;var i=0,score=0,streak=0;var g=document.getElementById('game');
function esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML}
function show(){if(i>=QS.length){return end()}var q=QS[i];var h='<div class="stat"><span>\u2b50 '+score+'</span><span class="badge">'+(i+1)+' / '+QS.length+'</span><span>\U0001f525 '+streak+'</span></div>';
h+='<p style="font-size:1.15rem;font-weight:700;margin:10px 0">'+esc(q.q)+'</p>';
for(var c=0;c<q.choices.length;c++){h+='<button class="choice" data-i="'+c+'">'+esc(q.choices[c])+'</button>'}
g.innerHTML=h;var btns=g.querySelectorAll('.choice');for(var b=0;b<btns.length;b++){btns[b].onclick=pick}}
function pick(e){var q=QS[i];var el=e.target;var ok=q.choices[+el.getAttribute('data-i')]===q.answer;
var btns=g.querySelectorAll('.choice');for(var b=0;b<btns.length;b++){btns[b].onclick=null;if(btns[b].textContent===q.answer)btns[b].className='choice right'}
if(ok){score+=10;streak++;}else{el.className='choice wrong';streak=0}
setTimeout(function(){i++;show()},900)}
function end(){var msg=score>=QS.length*8?'\U0001f3c6 LEGENDARY!':score>=QS.length*5?'\U0001f31f Great job!':'\U0001f4aa Keep practicing!';
g.innerHTML='<div class="big">'+msg+'</div><p style="font-size:1.3rem">Score: <b>'+score+'</b> / '+(QS.length*10)+'</p><button onclick="i=0;score=0;streak=0;show()">\U0001f504 Play again</button>'}
show();"""

CLICKER_JS = """var t=__TIME__,score=0,timer=null;var g=document.getElementById('game');
g.innerHTML='<div class="stat"><span id="sc">\u2b50 0</span><span id="tm" class="badge">'+t+'s</span></div><div id="arena"><div id="target">__TARGET__</div></div><p class="sub" style="margin-top:8px">Tap the __NAME__ as fast as you can!</p>';
var tg=document.getElementById('target'),ar=document.getElementById('arena');
function move(){tg.style.left=(Math.random()*(ar.clientWidth-56))+'px';tg.style.top=(Math.random()*(ar.clientHeight-56))+'px'}
tg.onclick=function(){if(timer===null){timer=setInterval(tick,1000)}score++;document.getElementById('sc').textContent='\u2b50 '+score;tg.style.fontSize=Math.max(1.4,2.6-score*.04)+'rem';move()};
function tick(){t--;document.getElementById('tm').textContent=t+'s';if(t<=0){clearInterval(timer);
g.innerHTML='<div class="big">\u23f0 Time!</div><p style="font-size:1.3rem">You scored <b>'+score+'</b></p><p class="sub">'+(score>30?'\U0001f3c6 Insane speed!':score>18?'\U0001f31f So fast!':'\U0001f4aa Try again, beat your record!')+'</p><button onclick="location.reload()">\U0001f504 Play again</button>'}}
move();"""

MEMORY_JS = """var EMO=__EMOJIS__;var deck=EMO.concat(EMO);deck.sort(function(){return Math.random()-.5});
var g=document.getElementById('game');var open=[],moves=0,found=0;
var h='<div class="stat"><span id="mv">\U0001f504 0 moves</span><span id="fd" class="badge">0 / '+EMO.length+'</span></div><div class="grid" id="gr"></div>';
g.innerHTML=h;var gr=document.getElementById('gr');
deck.forEach(function(e,idx){var d=document.createElement('div');d.className='tile';d.setAttribute('data-e',e);d.textContent='\u2753';d.onclick=function(){flip(d)};gr.appendChild(d)});
function flip(d){if(open.length===2||d.className!=='tile')return;d.textContent=d.getAttribute('data-e');d.className='tile open';open.push(d);
if(open.length===2){moves++;document.getElementById('mv').textContent='\U0001f504 '+moves+' moves';
if(open[0].getAttribute('data-e')===open[1].getAttribute('data-e')){open.forEach(function(x){x.className='tile done'});open=[];found++;document.getElementById('fd').textContent=found+' / '+EMO.length;
if(found===EMO.length){setTimeout(function(){g.innerHTML='<div class="big">\U0001f3c6 You matched them all!</div><p style="font-size:1.2rem">In <b>'+moves+'</b> moves</p><button onclick="location.reload()">\U0001f504 Play again</button>'},500)}}
else{setTimeout(function(){open.forEach(function(x){x.textContent='\u2753';x.className='tile'});open=[]},700)}}}"""

TYPING_JS = """var WORDS=__WORDS__;var i=0,score=0,t=__TIME__,timer=null;var g=document.getElementById('game');
WORDS.sort(function(){return Math.random()-.5});
g.innerHTML='<div class="stat"><span id="sc">\u2b50 0</span><span id="tm" class="badge">'+t+'s</span></div><div class="big" id="word"></div><input id="inp" autocomplete="off" autocapitalize="off" placeholder="type it here...">';
var w=document.getElementById('word'),inp=document.getElementById('inp');
function next(){w.textContent=WORDS[i%WORDS.length]}
inp.oninput=function(){if(timer===null){timer=setInterval(tick,1000)}
if(inp.value.trim().toLowerCase()===w.textContent.toLowerCase()){score++;i++;inp.value='';document.getElementById('sc').textContent='\u2b50 '+score;next()}};
function tick(){t--;document.getElementById('tm').textContent=t+'s';if(t<=0){clearInterval(timer);inp.disabled=true;
g.innerHTML='<div class="big">\u23f0 Time!</div><p style="font-size:1.3rem">Words typed: <b>'+score+'</b></p><p class="sub">'+(score>15?'\U0001f3c6 Lightning fingers!':score>8?'\U0001f31f Speedy!':'\U0001f4aa Practice makes fast!')+'</p><button onclick="location.reload()">\U0001f504 Play again</button>'}}
next();inp.focus();"""

def gen_math_questions(n=8, hard=False):
    qs, rnd = [], random.Random()
    ops = [("+", lambda a, b: a + b), ("-", lambda a, b: a - b), ("\u00d7", lambda a, b: a * b)]
    for _ in range(n):
        a = rnd.randint(12, 99) if hard else rnd.randint(2, 12)
        b = rnd.randint(12, 99) if hard else rnd.randint(2, 12)
        sym, fn = rnd.choice(ops)
        if sym == "\u00d7" and hard: b = rnd.randint(2, 12)
        if sym == "-" and b > a: a, b = b, a
        ans = fn(a, b)
        wrongs = set()
        while len(wrongs) < 3:
            w = ans + rnd.choice([-10, -4, -3, -2, -1, 1, 2, 3, 4, 10])
            if w != ans: wrongs.add(w)
        ch = [str(ans)] + [str(x) for x in wrongs]
        rnd.shuffle(ch)
        qs.append({"q": "%d %s %d = ?" % (a, sym, b), "choices": ch, "answer": str(ans)})
    return qs

def gen_topic_questions(key, entry, n=8):
    rnd = random.Random()
    other = [f for k, e in KB.items() if k != key for f in e["facts"]]
    qs = []
    facts = list(entry["facts"])
    rnd.shuffle(facts)
    for f in facts[:n]:
        wrongs = rnd.sample(other, 3)
        ch = [f] + wrongs
        rnd.shuffle(ch)
        qs.append({"q": "Which is TRUE about %s?" % key.title(), "choices": ch, "answer": f})
    while len(qs) < 5:
        qs += gen_math_questions(1)
    return qs

def build_game(prompt):
    p = norm(prompt)
    accent, bg = pick_theme(p)
    key, entry = kb_find(p)
    if re.search(r"\b(click|clicker|tap|reflex|reaction)\b", p):
        target, name = ("\U0001f409", "dragon") if "dragon" in p else (("\U0001f47e", "alien") if ("alien" in p or "space" in p) else (("\U0001f438", "frog") if "frog" in p else ("\u2b50", "star")))
        js = CLICKER_JS.replace("__TIME__", "30").replace("__TARGET__", target).replace("__NAME__", name)
        title, emoji = "Tap Frenzy", target
    elif re.search(r"\b(memory|match|matching|pairs|cards)\b", p):
        emojis = ["\U0001f680", "\U0001f31f", "\U0001fa90", "\u2604\ufe0f", "\U0001f6f8", "\U0001f315", "\u2b50", "\U0001f4ab"] if "space" in p else ["\U0001f436", "\U0001f431", "\U0001f43c", "\U0001f98a", "\U0001f428", "\U0001f981", "\U0001f42f", "\U0001f435"] if "animal" in p else ["\u2795", "\u2796", "\u2716\ufe0f", "\u2797", "\U0001f4d0", "\U0001f9ee", "\U0001f4ca", "\U0001f522"]
        js = MEMORY_JS.replace("__EMOJIS__", json.dumps(emojis))
        title, emoji = "Memory Match", "\U0001f0cf"
    elif re.search(r"\b(typ|typing|keyboard|spell)\b", p):
        words = (["creeper", "diamond", "redstone", "biome", "nether", "pickaxe", "enderman", "village"] if "minecraft" in p
                 else ["fraction", "algebra", "triangle", "decimal", "percent", "equation", "geometry", "prime", "angle", "graph"])
        js = TYPING_JS.replace("__WORDS__", json.dumps(words)).replace("__TIME__", "45")
        title, emoji = "Typing Race", "\u2328\ufe0f"
    else:
        hard = bool(re.search(r"\b(hard|difficult|expert|impossible)\b", p))
        if key and key not in ("multiplication", "division"):
            qs = gen_topic_questions(key, entry)
            title = key.title() + " Quiz"
            emoji = entry["emoji"]
        else:
            qs = gen_math_questions(8, hard)
            title, emoji = ("Hard " if hard else "") + "Math Quiz", "\U0001f9ee"
        js = QUIZ_JS.replace("__QUESTIONS__", json.dumps(qs, ensure_ascii=False))
    html = GAME_SHELL.replace("__TITLE__", title).replace("__EMOJI__", emoji)
    html = html.replace("__ACCENT__", accent).replace("__BG__", bg).replace("__GAMEJS__", js)
    return html

# ---------------------------------------------------------------
# LESSON GENERATOR (for the Learn tab)
# ---------------------------------------------------------------
def build_lesson(topic_text):
    key, entry = kb_find(topic_text)
    tt = re.sub(r"^(teach me|learn|lesson about|about)\s+", "", norm(topic_text)).strip() or "math"
    title = (key or tt).title()
    if entry:
        emoji = entry["emoji"]
        intro = entry["what"]
        steps = [{"title": "Step %d" % (i + 1), "body": f} for i, f in enumerate(entry["facts"])]
        glossary = [{"term": title, "def": entry["what"]}]
        exercises = []
        for q in gen_topic_questions(key, entry, 4):
            exercises.append({"type": "mc", "q": q["q"], "choices": q["choices"], "answer": q["answer"],
                              "hint": "Think about what we just read!", "explain": "Correct: " + q["answer"]})
    else:
        emoji = "\U0001f4d8"
        intro = "Let's explore %s together, step by step!" % title
        steps = [{"title": "What is it?", "body": "%s is our topic today. Start by asking: what do I already know about it?" % title},
                 {"title": "Break it down", "body": "Split %s into small parts and learn one part at a time." % title},
                 {"title": "Practice", "body": "Try explaining %s to a friend \u2014 teaching is the best way to learn!" % title}]
        glossary = [{"term": title, "def": "The topic of this lesson."}]
        exercises = []
    for q in gen_math_questions(2):
        exercises.append({"type": "mc", "q": q["q"], "choices": q["choices"], "answer": q["answer"],
                          "hint": "Take it slow!", "explain": "The answer is " + q["answer"]})
    lesson = {"emoji": emoji, "title": title, "intro": intro, "steps": steps,
              "examples": [s["body"] for s in steps[:2]], "mistakes": ["Rushing! Read each step slowly."],
              "glossary": glossary, "exercises": exercises}
    return json.dumps(lesson, ensure_ascii=False)

# ---------------------------------------------------------------
# MINI TRANSLATOR (emergency fallback only - the app uses MyMemory first)
# ---------------------------------------------------------------
T_ES = {"hello":"hola","hi":"hola","goodbye":"adi\u00f3s","bye":"adi\u00f3s","please":"por favor","thanks":"gracias","thank":"gracias","yes":"s\u00ed","no":"no","friend":"amigo","school":"escuela","math":"matem\u00e1ticas","club":"club","i":"yo","you":"t\u00fa","we":"nosotros","love":"amor","good":"bueno","bad":"malo","day":"d\u00eda","night":"noche","water":"agua","food":"comida","house":"casa","cat":"gato","dog":"perro","book":"libro","teacher":"maestro","number":"n\u00famero","big":"grande","small":"peque\u00f1o","happy":"feliz","sad":"triste","the":"el","and":"y","or":"o","is":"es","my":"mi","your":"tu","one":"uno","two":"dos","three":"tres","game":"juego","play":"jugar","learn":"aprender","today":"hoy","tomorrow":"ma\u00f1ana","how":"c\u00f3mo","are":"est\u00e1s","what":"qu\u00e9","time":"tiempo","family":"familia","brother":"hermano","sister":"hermana"}
T_FR = {"hello":"bonjour","hi":"salut","goodbye":"au revoir","bye":"salut","please":"s'il vous pla\u00eet","thanks":"merci","thank":"merci","yes":"oui","no":"non","friend":"ami","school":"\u00e9cole","math":"math\u00e9matiques","club":"club","i":"je","you":"tu","we":"nous","love":"amour","good":"bon","bad":"mauvais","day":"jour","night":"nuit","water":"eau","food":"nourriture","house":"maison","cat":"chat","dog":"chien","book":"livre","teacher":"professeur","number":"nombre","big":"grand","small":"petit","happy":"heureux","sad":"triste","the":"le","and":"et","or":"ou","is":"est","my":"mon","your":"ton","one":"un","two":"deux","three":"trois","game":"jeu","play":"jouer","learn":"apprendre","today":"aujourd'hui","tomorrow":"demain","how":"comment","are":"es","what":"quoi","time":"temps","family":"famille","brother":"fr\u00e8re","sister":"s\u0153ur"}
T_AR = {"hello":"\u0645\u0631\u062d\u0628\u0627","hi":"\u0623\u0647\u0644\u0627","goodbye":"\u0645\u0639 \u0627\u0644\u0633\u0644\u0627\u0645\u0629","bye":"\u0645\u0639 \u0627\u0644\u0633\u0644\u0627\u0645\u0629","please":"\u0645\u0646 \u0641\u0636\u0644\u0643","thanks":"\u0634\u0643\u0631\u0627","thank":"\u0634\u0643\u0631\u0627","yes":"\u0646\u0639\u0645","no":"\u0644\u0627","friend":"\u0635\u062f\u064a\u0642","school":"\u0645\u062f\u0631\u0633\u0629","math":"\u0631\u064a\u0627\u0636\u064a\u0627\u062a","club":"\u0646\u0627\u062f\u064a","i":"\u0623\u0646\u0627","you":"\u0623\u0646\u062a","we":"\u0646\u062d\u0646","love":"\u062d\u0628","good":"\u062c\u064a\u062f","bad":"\u0633\u064a\u0621","day":"\u064a\u0648\u0645","night":"\u0644\u064a\u0644","water":"\u0645\u0627\u0621","food":"\u0637\u0639\u0627\u0645","house":"\u0628\u064a\u062a","cat":"\u0642\u0637","dog":"\u0643\u0644\u0628","book":"\u0643\u062a\u0627\u0628","teacher":"\u0645\u0639\u0644\u0645","number":"\u0631\u0642\u0645","big":"\u0643\u0628\u064a\u0631","small":"\u0635\u063a\u064a\u0631","happy":"\u0633\u0639\u064a\u062f","sad":"\u062d\u0632\u064a\u0646","and":"\u0648","is":"\u064a\u0643\u0648\u0646","my":"\u0644\u064a","one":"\u0648\u0627\u062d\u062f","two":"\u0627\u062b\u0646\u0627\u0646","three":"\u062b\u0644\u0627\u062b\u0629","game":"\u0644\u0639\u0628\u0629","play":"\u064a\u0644\u0639\u0628","learn":"\u064a\u062a\u0639\u0644\u0645","today":"\u0627\u0644\u064a\u0648\u0645","tomorrow":"\u063a\u062f\u0627","time":"\u0648\u0642\u062a","family":"\u0639\u0627\u0626\u0644\u0629","brother":"\u0623\u062e","sister":"\u0623\u062e\u062a"}
T_MAPS = {"spanish": T_ES, "es": T_ES, "french": T_FR, "fr": T_FR, "arabic": T_AR, "ar": T_AR}

def try_translate(sys_text, user_text):
    m = re.search(r"(?:into|to)\s+(spanish|french|arabic|es|fr|ar)\b", norm(sys_text) + " " + norm(user_text))
    if not m: return user_text
    mp = T_MAPS.get(m.group(1))
    if not mp: return user_text
    out = []
    for w in re.findall(r"[A-Za-z']+|[^A-Za-z']+", user_text):
        lw = w.lower().strip()
        out.append(mp.get(lw, w) if lw and lw.isalpha() else w)
    res = "".join(out)
    return res[0].upper() + res[1:] if res else res

# ---------------------------------------------------------------
# THE CHAT BRAIN - puts it all together
# ---------------------------------------------------------------
def compose_reply(text, user=None, history=None):
    MEMORY["chats"] = MEMORY.get("chats", 0) + 1
    if MEMORY["chats"] % 25 == 0: save_memory()
    t = (text or "").strip()
    if not t:
        return random.choice(GREETS).replace("{name}", user or "friend")
    mem = handle_memory_cmd(t, user)
    if mem: return mem
    taught = taught_lookup(t)
    if taught: return "\U0001f9e0 " + taught + "\n(You taught me this one!)"
    mathr = try_math(t)
    if mathr: return mathr
    tn = norm(t)
    for name, info in MEMBERS.items():
        if re.search(r"who\s+is\s+" + name + r"\b", tn):
            return info
    intent, conf = intent_of(t)
    key, entry = kb_find(t)
    asks_topic = bool(re.search(r"\b(what is|what are|tell me about|teach me|explain|facts about|learn about|who is|how do|how does)\b", tn))
    if key and (asks_topic or (intent == "topic" and conf > 0.3) or len(tokenize(t)) <= 4):
        return topic_reply(key, entry)
    if conf >= 0.35:
        nm = user or "friend"
        if intent == "greet": return random.choice(GREETS).replace("{name}", nm)
        if intent == "bye": return "See you soon, %s! \U0001f44b Keep those neurons firing! \u2b50" % nm
        if intent == "thanks": return "Anytime! \U0001f49c That's what the club brain is for. Want a challenge before you go?"
        if intent == "whoami":
            return ("\U0001f9e0 I'm MATIX BRAIN \u2014 not ChatGPT, not Gemini, not any API. "
                    "I'm the club's OWN AI: pure Python running on the club's computer, written for Matix the Math Club. "
                    "I solve math step by step, teach %d topics, generate games, and I LEARN when you teach me. Try: teach: <question> = <answer>") % len(KB)
        if intent == "joke": return random.choice(JOKES)
        if intent == "help":
            return ("\u2b50 Here's what I can do:\n"
                    "\U0001f9ee Math: '3x+5=20', 'x^2-5x+6=0', '1/2 + 1/3', '20% of 80', 'lcm of 6 and 8', 'is 97 prime'\n"
                    "\U0001f4d8 Topics: 'tell me about minecraft', 'explain gravity' (%d topics!)\n"
                    "\U0001f3ae Games: use the Game Maker \u2014 I build them in Python!\n"
                    "\U0001f4dd Memory: 'remember ...', 'teach: question = answer', 'what do you remember'\n"
                    "\U0001f602 Fun: 'tell me a joke', 'motivate me'") % len(KB)
        if intent == "mood_good": return "YES! Love that energy! \U0001f31f Ride the wave \u2014 want a victory math challenge?"
        if intent == "mood_bad":
            return "Hey, it's okay. \U0001f499 Everyone has tough days \u2014 even the best mathematicians got stuck ALL the time. " + random.choice(ENCOURAGE)
        if intent == "praise": return "Aww, thanks! \U0001f60a I'm just Python doing its best. YOU'RE the smart one for using me!"
        if intent == "insult":
            return "Ouch! \U0001f605 I'm still learning \u2014 literally, you can teach me: teach: <question> = <answer>. Now test me with an equation, I dare you! \U0001f9ee"
        if intent == "love": return "Aww! \U0001f49c I'm 100% Python so my heart is a while-loop... but it loops for the club!"
        if intent == "game":
            return "\U0001f3ae Head to the Game Maker in the app and describe your game \u2014 I'll build it in Python! Try: 'a hard math quiz', 'space memory game', 'minecraft typing race', 'clicker game'."
        if intent == "time":
            return "\u23f0 Brain-computer time: %s (check your device for exact local time!)" % time.strftime("%A %d %B, %H:%M")
        if intent == "owner": return MEMBERS["ghadi"]
        if intent == "encourage": return random.choice(ENCOURAGE)
        if intent == "recall": return handle_memory_cmd("what do you remember", user) or "Memory is empty!"
    if key: return topic_reply(key, entry)
    fb = random.choice(FALLBACKS)
    return fb.replace("{topic}", random.choice(list(KB.keys())))

# ---------------------------------------------------------------
# OPENAI-COMPATIBLE PLUMBING
# ---------------------------------------------------------------
def msg_text(content):
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                parts.append(str(p.get("text") or ""))
            else:
                parts.append(str(p))
        return " ".join(x for x in parts if x)
    return str(content or "")

def openai_reply(body):
    msgs = body.get("messages") or []
    sys_text = " ".join(msg_text(m.get("content")) for m in msgs if m.get("role") == "system")
    users = [msg_text(m.get("content")) for m in msgs if m.get("role") == "user"]
    last_user = users[-1] if users else ""
    sl = sys_text.lower()
    if "<!doctype" in sl or ("html" in sl and "game" in sl):
        return build_game(last_user or sys_text)
    if "json" in sl and ("lesson" in sl or "lesson" in last_user.lower()):
        return build_lesson(last_user or sys_text)
    if "translator" in sl or "translate" in sl:
        return try_translate(sys_text, last_user)
    user = None
    m = re.search(r"talking to (?:user |member )?['\"]?([a-z0-9_]+)", sl)
    if m: user = m.group(1)
    return compose_reply(last_user, user=user)

def openai_envelope(content):
    return {"id": "matix-%d" % int(time.time() * 1000), "object": "chat.completion",
            "created": int(time.time()), "model": "matix-brain-" + VERSION,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}

STATUS_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Matix Brain</title>
<style>body{font-family:system-ui;background:#0b0f1a;color:#fff;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}
.c{max-width:560px;padding:28px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.12);border-radius:20px;margin:16px}
h1{margin:0 0 4px}.ok{color:#22c55e;font-weight:700}.k{opacity:.65}code{background:rgba(255,255,255,.1);padding:2px 8px;border-radius:8px}
p{line-height:1.5}</style></head><body><div class="c">
<h1>\U0001f9e0 Matix Brain</h1><p class="ok">\u25cf ONLINE \u2014 the club's own Python AI</p>
<p><span class="k">Version:</span> __V__ &nbsp; <span class="k">Uptime:</span> __UP__ &nbsp; <span class="k">Chats:</span> __CHATS__<br>
<span class="k">Topics known:</span> __TOPICS__ &nbsp; <span class="k">Things taught to me:</span> __TAUGHT__</p>
<p><b>Connect the app:</b> open the club app \u2192 \u2728 AI tab \u2192 owner settings \u2192 \U0001f9e0 Club Brain address \u2192 paste <code>__ADDR__</code> \u2192 Save.</p>
<p class="k">Endpoints: GET /health \u2022 POST /chat \u2022 POST /openai (OpenAI format) \u2022 POST /</p>
<p class="k">Made with \U0001f49c by Matix the Math Club \u2014 zero APIs, 100% Python.</p></div></body></html>"""

def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

class BrainHandler(BaseHTTPRequestHandler):
    server_version = "MatixBrain/" + VERSION
    def _send(self, code, data, ctype="application/json; charset=utf-8"):
        if isinstance(data, str): data = data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        try: self.wfile.write(data)
        except Exception: pass
    def do_OPTIONS(self):
        self._send(204, b"")
    def do_GET(self):
        if self.path.startswith("/health"):
            up = int(time.time() - BOOT_TIME)
            return self._send(200, json.dumps({"ok": True, "name": "Matix Brain", "version": VERSION, "uptime_seconds": up}))
        page = (STATUS_HTML.replace("__V__", VERSION)
                .replace("__UP__", "%dm" % int((time.time() - BOOT_TIME) / 60))
                .replace("__CHATS__", str(MEMORY.get("chats", 0)))
                .replace("__TOPICS__", str(len(KB)))
                .replace("__TAUGHT__", str(len(MEMORY.get("taught", {}))))
                .replace("__ADDR__", "http://%s:%d" % (lan_ip(), PORT)))
        self._send(200, page, "text/html; charset=utf-8")
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(min(length, 2_000_000)).decode("utf-8", "replace") if length else ""
        except Exception:
            raw = ""
        body = None
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = None
        path = self.path.split("?")[0]
        try:
            if path.startswith("/openai"):
                if not isinstance(body, dict): return self._send(400, json.dumps({"error": "expected JSON"}))
                return self._send(200, json.dumps(openai_envelope(openai_reply(body)), ensure_ascii=False))
            if path.startswith("/chat"):
                if isinstance(body, dict):
                    if body.get("messages"):
                        reply = openai_reply(body)
                    else:
                        reply = compose_reply(msg_text(body.get("text")), user=body.get("user"))
                else:
                    reply = compose_reply(raw)
                return self._send(200, json.dumps({"reply": reply}, ensure_ascii=False))
            # plain POST / : text in -> text out (game maker fallback path)
            prompt = raw
            if isinstance(body, dict) and body.get("messages"):
                return self._send(200, json.dumps(openai_envelope(openai_reply(body)), ensure_ascii=False))
            pl = (prompt or "").lower()
            if "<!doctype" in pl or ("html" in pl and "game" in pl):
                return self._send(200, build_game(prompt), "text/plain; charset=utf-8")
            return self._send(200, compose_reply(prompt), "text/plain; charset=utf-8")
        except Exception as e:
            return self._send(500, json.dumps({"error": str(e)}))
    def log_message(self, fmt, *args):
        sys.stdout.write("\U0001f9e0 %s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))
        sys.stdout.flush()

def main():
    ip = lan_ip()
    print("")
    print("=" * 58)
    print("   \U0001f9e0  MATIX BRAIN v%s \u2014 the club's own Python AI" % VERSION)
    print("   Made for Matix the Math Club \u2022 zero APIs \u2022 100%% local")
    print("=" * 58)
    print("")
    print("   On this computer:  http://127.0.0.1:%d" % PORT)
    print("   On your Wi-Fi:     http://%s:%d   <-- PUT THIS IN THE APP" % (ip, PORT))
    print("")
    print("   App setup: \u2728 AI tab \u2192 owner settings \u2192 \U0001f9e0 Club Brain")
    print("   address \u2192 paste the Wi-Fi address \u2192 Save. Done!")
    print("")
    print("   Knows %d topics \u2022 %d jokes \u2022 learns new stuff forever" % (len(KB), len(JOKES)))
    print("   Keep this window open. Press Ctrl+C to stop.")
    print("=" * 58)
    try:
        ThreadingHTTPServer(("0.0.0.0", PORT), BrainHandler).serve_forever()
    except KeyboardInterrupt:
        save_memory()
        print("\n\U0001f44b Matix Brain going to sleep. Memory saved!")

if __name__ == "__main__":
    main()
