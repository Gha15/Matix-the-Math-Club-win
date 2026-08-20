==============================================
 MATIX BRAIN v1.0 - the club's own Python AI
 Matix the Math Club (owner: Ghadi)
==============================================

WHAT IS THIS?
  matix_brain.py is a full AI server written in pure Python.
  No ChatGPT. No Gemini. No API keys. No external AI at all.
  Every answer is generated on YOUR computer, by YOUR code.

WHAT DO I NEED?
  Just Python 3.9 or newer (free from https://python.org).
  No pip installs needed. Nothing else.

HOW TO START IT
  Windows:  double-click  start_windows.bat
  Mac:      double-click  start_mac.command
            (first time: right-click -> Open, because it's unsigned)
  Any OS:   python3 matix_brain.py

  It will print something like:
     On your Wi-Fi:  http://192.168.1.20:8787   <-- PUT THIS IN THE APP

CONNECT THE CLUB APP (one time, by the owner)
  1. Open the club app on a device ON THE SAME WI-FI.
  2. Go to the AI tab -> open the owner settings section.
  3. Paste the address into "Club Brain address" -> Save.
  4. Done! It saves to Firebase, so EVERY member's app now uses
     the brain automatically. AI chat, Game Maker, Learn AI and
     translator fallback all route to your Python.

WHAT CAN IT DO?
  * Chat with club personality (intent engine + a tiny neural
    network that trains itself with backpropagation at startup)
  * Real math with steps: 3x+5=20, x^2-5x+6=0, 1/2+1/3,
    20% of 80, lcm of 6 and 8, is 97 prime, times tables...
  * Teach 50+ topics (minecraft, space, animals, countries...)
  * Generate PLAYABLE games in the Game Maker (quiz, clicker,
    memory match, typing race) - built by Python, not by an API
  * Learn forever:
      teach: what is our motto = math is power
      remember the tournament is saturday
      what do you remember
  * Jokes, motivation, and zero judgment

GOOD TO KNOW
  * Keep the window open - closing it puts the brain to sleep.
    (The app then falls back to the free club AI automatically.)
  * Phones can't run Python inside apps, so the brain lives on a
    computer and the apps talk to it over Wi-Fi. Real AIs work
    the same way - they always run on a server!
  * Memory is saved in matix_brain_memory.json next to the file.
  * Change the port: set MATIX_BRAIN_PORT=9000 before starting.
  * Endpoints: GET /health, POST /chat, POST /openai, POST /

HONEST NOTE ON "100,000 LINES"
  Smartness doesn't come from line count. Big AIs are actually
  small programs trained on giant mountains of data with huge
  computers. This brain is ~1,300 real lines where every line
  does something. Padding it to 100,000 lines would only make
  it slower, not smarter. Quality > quantity - that's math. ;)

Made with love, by the club, for the club.  MATH IS POWER!
