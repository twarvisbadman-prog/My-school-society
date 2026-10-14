# quiz.py
# ============================================================
# Daily Quiz Engine — Student Hub
# 100 questions across 6 categories.
# Rotation: cycles through the bank every N days.
# Options shuffle per day for freshness.
# No DB, no external calls, no cost.
# ============================================================

import random
from datetime import date


# ============================================================
# QUESTION BANK — 100 QUESTIONS
# ============================================================
# Rules:
#   - "a" must EXACTLY match one entry in "options"
#   - 4 options per question
#   - "subject" is one of: logic, math, reasoning, common, word, science
# ============================================================
QUIZ_BANK = [
    # ═══════════════════════════════════════════════════════
    # LOGIC & DEDUCTION (Q1–Q18)
    # ═══════════════════════════════════════════════════════
    {
        "q": "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost?",
        "a": "$0.05",
        "options": ["$0.10", "$0.05", "$0.01", "$1.00"],
        "subject": "logic",
    },
    {
        "q": "A farmer has 17 sheep. All but 9 run away. How many sheep are left?",
        "a": "9",
        "options": ["8", "9", "17", "0"],
        "subject": "logic",
    },
    {
        "q": "You're running a race and you overtake the person in 2nd place. What place are you in now?",
        "a": "2nd",
        "options": ["1st", "2nd", "3rd", "Last"],
        "subject": "logic",
    },
    {
        "q": "A rooster sits on the peak of a barn's roof facing West. It lays an egg. Which direction does the egg roll?",
        "a": "Roosters don't lay eggs",
        "options": ["East", "West", "Straight down", "Roosters don't lay eggs"],
        "subject": "logic",
    },
    {
        "q": "Two fathers and two sons go fishing. Each catches one fish. They catch 3 fish total. How is this possible?",
        "a": "They're a grandfather, father, and son",
        "options": [
            "They're a grandfather, father, and son",
            "One fish was already in the boat",
            "They shared a fishing rod",
            "One of them lied",
        ],
        "subject": "logic",
    },
    {
        "q": "You have 9 identical-looking coins. One is slightly heavier. What's the minimum number of weighings on a balance scale to find it?",
        "a": "2",
        "options": ["1", "2", "3", "4"],
        "subject": "logic",
    },
    {
        "q": "You flip a fair coin 5 times and get heads every time. What's the probability of getting heads on the 6th flip?",
        "a": "50%",
        "options": ["Less than 50%", "50%", "More than 50%", "0%"],
        "subject": "logic",
    },
    {
        "q": "What gets wetter and wetter the more it dries?",
        "a": "A towel",
        "options": ["A sponge", "A towel", "A river", "A cloud"],
        "subject": "logic",
    },
    {
        "q": "A doctor gives you 3 pills and says take one every 30 minutes. How long until you finish them all?",
        "a": "1 hour",
        "options": ["30 minutes", "1 hour", "1.5 hours", "3 hours"],
        "subject": "logic",
    },
    {
        "q": "How many times can you subtract 5 from 25?",
        "a": "Only once",
        "options": ["5 times", "Only once", "25 times", "Infinitely"],
        "subject": "logic",
    },
    {
        "q": "If you have a bowl with 6 apples and you take away 4, how many apples do you have?",
        "a": "4",
        "options": ["2", "4", "6", "10"],
        "subject": "logic",
    },
    {
        "q": "What is the minimum number of straight lines needed to divide a circle into 8 parts?",
        "a": "4",
        "options": ["3", "4", "7", "8"],
        "subject": "logic",
    },
    {
        "q": "You're in a dark room with a candle, a kerosene lamp, and a fireplace. You have only one match. Which do you light first?",
        "a": "The match",
        "options": ["The candle", "The kerosene lamp", "The fireplace", "The match"],
        "subject": "logic",
    },
    {
        "q": "A logician's wife tells him, 'If I ask you to come home early tonight, will you?' He says, 'Yes.' She asks, 'Come home early tonight.' He stays out late. Why?",
        "a": "He wasn't obligated by his 'yes' — she only asked if he would, not to do it",
        "options": [
            "He forgot",
            "He wasn't obligated by his 'yes' — she only asked if he would, not to do it",
            "He doesn't love her",
            "The question was unclear",
        ],
        "subject": "logic",
    },
    {
        "q": "Every person in a room shakes hands with every other person exactly once. If there are 10 people, how many handshakes occur?",
        "a": "45",
        "options": ["45", "50", "90", "100"],
        "subject": "logic",
    },
    {
        "q": "A drawer contains 10 black and 10 white socks. How many socks must you pull out in the dark to be sure of having a matching pair?",
        "a": "3",
        "options": ["2", "3", "10", "11"],
        "subject": "logic",
    },
    {
        "q": "Three switches outside a room control three bulbs inside. You may enter the room only once. How do you determine which switch controls which bulb?",
        "a": "Turn on one switch, wait, turn it off, turn on another, then enter",
        "options": [
            "Impossible with one entry",
            "Turn on one switch, wait, turn it off, turn on another, then enter",
            "Flip switches randomly",
            "Use a voltmeter",
        ],
        "subject": "logic",
    },
    {
        "q": "A man pushes his car to a hotel and knows immediately that he's bankrupt. How?",
        "a": "He's playing Monopoly",
        "options": ["He saw the hotel bill", "He's playing Monopoly", "He got a call", "He lost his wallet"],
        "subject": "logic",
    },

    # ═══════════════════════════════════════════════════════
    # MATH & NUMBERS (Q19–Q36)
    # ═══════════════════════════════════════════════════════
    {
        "q": "A father is 4 times as old as his son. In 20 years, the father will be twice as old as his son. How old is the son now?",
        "a": "10",
        "options": ["5", "10", "15", "20"],
        "subject": "math",
    },
    {
        "q": "A clock strikes 6 in 5 seconds. How long does it take to strike 12?",
        "a": "11 seconds",
        "options": ["10 seconds", "11 seconds", "12 seconds", "22 seconds"],
        "subject": "math",
    },
    {
        "q": "Which weighs more: a kilogram of feathers, or a kilogram of steel?",
        "a": "They weigh the same",
        "options": ["Feathers", "Steel", "They weigh the same", "Depends on gravity"],
        "subject": "math",
    },
    {
        "q": "What is the smallest number of people needed to have a 50% chance that two of them share the same birthday?",
        "a": "23",
        "options": ["183", "100", "57", "23"],
        "subject": "math",
    },
    {
        "q": "If a chicken and a half lays an egg and a half in a day and a half, how many eggs will 6 chickens lay in 6 days?",
        "a": "24",
        "options": ["18", "24", "36", "6"],
        "subject": "math",
    },
    {
        "q": "What number, when multiplied by itself, gives 144?",
        "a": "12",
        "options": ["11", "12", "13", "14"],
        "subject": "math",
    },
    {
        "q": "If 3 cats catch 3 mice in 3 minutes, how many cats catch 100 mice in 100 minutes?",
        "a": "3",
        "options": ["3", "33", "100", "300"],
        "subject": "math",
    },
    {
        "q": "The sum of three consecutive even numbers is 48. What is the largest number?",
        "a": "18",
        "options": ["14", "16", "18", "20"],
        "subject": "math",
    },
    {
        "q": "A train travels 60 km in 30 minutes. What's its average speed?",
        "a": "120 km/h",
        "options": ["60 km/h", "90 km/h", "120 km/h", "180 km/h"],
        "subject": "math",
    },
    {
        "q": "Divide 30 by 1/2 and add 10. What do you get?",
        "a": "70",
        "options": ["25", "40", "70", "85"],
        "subject": "math",
    },
    {
        "q": "How much dirt is in a hole that is 3 feet by 3 feet by 3 feet?",
        "a": "None — it's a hole",
        "options": ["27 cubic feet", "9 cubic feet", "None — it's a hole", "3 cubic feet"],
        "subject": "math",
    },
    {
        "q": "If 5 machines take 5 minutes to make 5 widgets, how long do 100 machines take to make 100 widgets?",
        "a": "5 minutes",
        "options": ["5 minutes", "100 minutes", "20 minutes", "1 minute"],
        "subject": "math",
    },
    {
        "q": "What is the next number in the sequence: 1, 1, 2, 3, 5, 8, ___?",
        "a": "13",
        "options": ["10", "11", "12", "13"],
        "subject": "math",
    },
    {
        "q": "How many 3-cent stamps are in a dozen?",
        "a": "12",
        "options": ["4", "12", "36", "48"],
        "subject": "math",
    },
    {
        "q": "What is 1000 + 40 + 1000 + 30 + 1000 + 20 + 1000 + 10?",
        "a": "4100",
        "options": ["5000", "4100", "4000", "4200"],
        "subject": "math",
    },
    {
        "q": "A snail climbs 3 meters up a wall during the day and slides 2 meters back at night. The wall is 10 meters tall. How many days does it take to reach the top?",
        "a": "8 days",
        "options": ["7 days", "8 days", "10 days", "20 days"],
        "subject": "math",
    },
    {
        "q": "If you multiply any number by 0, the answer is always what?",
        "a": "0",
        "options": ["1", "0", "The number itself", "Undefined"],
        "subject": "math",
    },
    {
        "q": "What is the next number in the sequence: 2, 6, 12, 20, 30, ___?",
        "a": "42",
        "options": ["36", "40", "42", "48"],
        "subject": "math",
    },

    # ═══════════════════════════════════════════════════════
    # REASONING & RIDDLES (Q37–Q64)
    # ═══════════════════════════════════════════════════════
    {
        "q": "A man rode into town on Friday, stayed three days, and rode out on Friday. How?",
        "a": "His horse is named Friday",
        "options": ["The week has two Fridays", "His horse is named Friday", "He time-traveled", "He stayed 4 days"],
        "subject": "reasoning",
    },
    {
        "q": "A woman gives birth to twins — two boys, same father, same mother, same day. But they're not twins. How?",
        "a": "They're triplets (or more)",
        "options": ["They're adopted", "They're triplets (or more)", "Different fathers", "Different years"],
        "subject": "reasoning",
    },
    {
        "q": "Two people played 5 games of chess. Each won 3 games. How is that possible?",
        "a": "They didn't play against each other",
        "options": ["One cheated", "They didn't play against each other", "It's impossible", "They tied once"],
        "subject": "reasoning",
    },
    {
        "q": "A window cleaner is cleaning the windows of a 30-story building. He falls but isn't hurt. Why?",
        "a": "He fell off the first rung",
        "options": ["He had a rope", "He fell off the first rung", "He landed on a mattress", "He was wearing a suit"],
        "subject": "reasoning",
    },
    {
        "q": "A man walks into a bar and asks for a glass of water. The bartender pulls out a gun. The man thanks him and leaves. Why?",
        "a": "He had hiccups",
        "options": ["The bar was closing", "He had hiccups", "It was a joke", "He owed money"],
        "subject": "reasoning",
    },
    {
        "q": "What has cities but no houses, forests but no trees, and water but no fish?",
        "a": "A map",
        "options": ["A dream", "A map", "A painting", "A mirror"],
        "subject": "reasoning",
    },
    {
        "q": "The person who makes it sells it. The person who buys it never uses it. The person who uses it doesn't know it. What is it?",
        "a": "A coffin",
        "options": ["A cake", "A coffin", "A book", "A phone"],
        "subject": "reasoning",
    },
    {
        "q": "I speak without a mouth and hear without ears. I have no body, but I come alive with wind. What am I?",
        "a": "An echo",
        "options": ["A ghost", "An echo", "A shadow", "A thought"],
        "subject": "reasoning",
    },
    {
        "q": "A man lives in a small hut. All four walls face south. A bear walks by. What color is the bear?",
        "a": "White",
        "options": ["Brown", "Black", "White", "Grey"],
        "subject": "reasoning",
    },
    {
        "q": "A man is looking at a picture and says, 'Brothers and sisters I have none, but that man's father is my father's son.' Who is in the picture?",
        "a": "His son",
        "options": ["His father", "His brother", "His son", "His uncle"],
        "subject": "reasoning",
    },
    {
        "q": "What can travel around the world while staying in a corner?",
        "a": "A stamp",
        "options": ["A letter", "A stamp", "A plane", "A dream"],
        "subject": "reasoning",
    },
    {
        "q": "The more you take, the more you leave behind. What am I?",
        "a": "Footsteps",
        "options": ["Time", "Footsteps", "Money", "Shadows"],
        "subject": "reasoning",
    },
    {
        "q": "What has many keys but can't open a single lock?",
        "a": "A piano",
        "options": ["A map", "A piano", "A keyboard", "A ring"],
        "subject": "reasoning",
    },
    {
        "q": "I'm tall when I'm young and short when I'm old. What am I?",
        "a": "A candle",
        "options": ["A tree", "A candle", "A man", "A mountain"],
        "subject": "reasoning",
    },
    {
        "q": "What has a head, a tail, but no body?",
        "a": "A coin",
        "options": ["A snake", "A coin", "A shadow", "A comet"],
        "subject": "reasoning",
    },
    {
        "q": "What comes down but never goes up?",
        "a": "Rain",
        "options": ["Sunlight", "Rain", "Wind", "Sound"],
        "subject": "reasoning",
    },
    {
        "q": "What breaks as soon as you name it?",
        "a": "Silence",
        "options": ["Glass", "Silence", "A promise", "A record"],
        "subject": "reasoning",
    },
    {
        "q": "What is full of holes but still holds water?",
        "a": "A sponge",
        "options": ["A net", "A sponge", "A sieve", "A basket"],
        "subject": "reasoning",
    },
    {
        "q": "What goes up but never comes down?",
        "a": "Your age",
        "options": ["A balloon", "Your age", "Smoke", "A rocket"],
        "subject": "reasoning",
    },
    {
        "q": "What can fill a room but takes up no space?",
        "a": "Light",
        "options": ["Air", "Light", "Water", "Noise"],
        "subject": "reasoning",
    },
    {
        "q": "What has a thumb and four fingers but is not alive?",
        "a": "A glove",
        "options": ["A hand", "A glove", "A paw", "A statue"],
        "subject": "reasoning",
    },
    {
        "q": "What gets bigger the more you take away from it?",
        "a": "A hole",
        "options": ["A mountain", "A hole", "A debt", "A shadow"],
        "subject": "reasoning",
    },
    {
        "q": "What has one eye but can't see?",
        "a": "A needle",
        "options": ["A storm", "A needle", "A cyclops", "A potato"],
        "subject": "reasoning",
    },
    {
        "q": "What can you catch but not throw?",
        "a": "A cold",
        "options": ["A ball", "A cold", "A fish", "A shadow"],
        "subject": "reasoning",
    },
    {
        "q": "What runs but never walks, has a bed but never sleeps?",
        "a": "A river",
        "options": ["A car", "A river", "A clock", "A computer"],
        "subject": "reasoning",
    },
    {
        "q": "What kind of band never plays music?",
        "a": "A rubber band",
        "options": ["A rock band", "A rubber band", "A jazz band", "A marching band"],
        "subject": "reasoning",
    },
    {
        "q": "You see a boat filled with people. It hasn't sunk, but when you look again, there's not a single person on it. Why?",
        "a": "They're all married",
        "options": ["They jumped out", "They're all married", "It sank", "It's a submarine"],
        "subject": "reasoning",
    },
    {
        "q": "What is always in front of you but can't be seen?",
        "a": "The future",
        "options": ["Air", "The future", "A shadow", "Your nose"],
        "subject": "reasoning",
    },

    # ═══════════════════════════════════════════════════════
    # COMMON SENSE (Q65–Q76)
    # ═══════════════════════════════════════════════════════
    {
        "q": "Before Mount Everest was discovered, what was the highest mountain on Earth?",
        "a": "Mount Everest",
        "options": ["K2", "Mount Everest", "Kangchenjunga", "Mount Kilimanjaro"],
        "subject": "common",
    },
    {
        "q": "How many months have 28 days?",
        "a": "All 12 months",
        "options": ["1", "2", "6", "All 12 months"],
        "subject": "common",
    },
    {
        "q": "If you throw a red stone into the blue sea, what does it become?",
        "a": "Wet",
        "options": ["Wet", "Blue", "Purple", "Heavier"],
        "subject": "common",
    },
    {
        "q": "Which is heavier: 1 kilogram of lead or 1 kilogram of cotton?",
        "a": "They weigh the same",
        "options": ["Lead", "Cotton", "They weigh the same", "Depends on shape"],
        "subject": "common",
    },
    {
        "q": "What has hands but cannot clap?",
        "a": "A clock",
        "options": ["A statue", "A clock", "A robot", "A tree"],
        "subject": "common",
    },
    {
        "q": "What has a face and two hands but no arms or legs?",
        "a": "A clock",
        "options": ["A doll", "A clock", "A robot", "A chair"],
        "subject": "common",
    },
    {
        "q": "How many animals did Moses take on the ark?",
        "a": "None — Noah built the ark",
        "options": ["Two of each", "Seven of each clean animal", "None — Noah built the ark", "One pair"],
        "subject": "common",
    },
    {
        "q": "If two hours ago it was as long after 1 PM as it was before 1 AM, what time is it now?",
        "a": "9 PM",
        "options": ["5 PM", "7 PM", "9 PM", "11 PM"],
        "subject": "common",
    },
    {
        "q": "A cowboy rides into town on Tuesday, stays 3 nights, and leaves on Tuesday. How?",
        "a": "His horse is named Tuesday",
        "options": ["He stayed 2 nights", "His horse is named Tuesday", "It's a leap year", "He lied"],
        "subject": "common",
    },
    {
        "q": "How many birthdays does the average person have?",
        "a": "One",
        "options": ["One per year", "One", "Many", "Depends"],
        "subject": "common",
    },
    {
        "q": "If you have a match and enter a dark room with a candle, a kerosene lamp, and a fireplace, which do you light first?",
        "a": "The match",
        "options": ["The candle", "The lamp", "The fireplace", "The match"],
        "subject": "common",
    },
    {
        "q": "What occurs once in a minute, twice in a moment, but never in a thousand years?",
        "a": "The letter M",
        "options": ["The letter E", "The letter M", "A second", "A heartbeat"],
        "subject": "common",
    },

    # ═══════════════════════════════════════════════════════
    # WORD & LANGUAGE (Q77–Q88)
    # ═══════════════════════════════════════════════════════
    {
        "q": "What word becomes shorter when you add two letters to it?",
        "a": "Short",
        "options": ["Tall", "Short", "Long", "Small"],
        "subject": "word",
    },
    {
        "q": "How many times does the letter 'E' appear in the sentence 'The quick brown fox jumps over the lazy dog'?",
        "a": "3",
        "options": ["2", "3", "4", "5"],
        "subject": "word",
    },
    {
        "q": "What is at the end of a rainbow?",
        "a": "The letter W",
        "options": ["Gold", "The letter W", "A leprechaun", "A pot"],
        "subject": "word",
    },
    {
        "q": "How many letters are in 'the alphabet'?",
        "a": "11",
        "options": ["26", "11", "8", "5"],
        "subject": "word",
    },
    {
        "q": "What occurs once in every minute, twice in every moment, yet never in a thousand years?",
        "a": "The letter M",
        "options": ["A second", "The letter M", "A heartbeat", "The letter T"],
        "subject": "word",
    },
    {
        "q": "Which word in the English language has the most definitions?",
        "a": "Set",
        "options": ["Run", "Go", "Set", "Take"],
        "subject": "word",
    },
    {
        "q": "What five-letter word becomes shorter when you add two letters to it?",
        "a": "Short",
        "options": ["Brief", "Small", "Short", "Long"],
        "subject": "word",
    },
    {
        "q": "What word is spelled the same forwards, backwards, and upside-down?",
        "a": "NOON",
        "options": ["MOM", "NOON", "WOW", "DAD"],
        "subject": "word",
    },
    {
        "q": "How many times does the letter 'F' appear in this sentence: 'Finished files are the result of years of scientific study combined with the experience of years.'?",
        "a": "6",
        "options": ["3", "4", "5", "6"],
        "subject": "word",
    },
    {
        "q": "What is the longest word that can be typed using only the left hand on a standard QWERTY keyboard?",
        "a": "Stewardesses",
        "options": ["Typewriter", "Stewardesses", "Qwerty", "Repertoire"],
        "subject": "word",
    },
    {
        "q": "What is the only common English word that ends in 'mt'?",
        "a": "Dreamt",
        "options": ["Meant", "Dreamt", "Attempt", "Exempt"],
        "subject": "word",
    },
    {
        "q": "What English word has three consecutive double letters?",
        "a": "Bookkeeper",
        "options": ["Committee", "Bookkeeper", "Mississippi", "Tennessee"],
        "subject": "word",
    },

    # ═══════════════════════════════════════════════════════
    # SCIENCE & NATURE (Q89–Q100)
    # ═══════════════════════════════════════════════════════
    {
        "q": "Which is hotter: a cup of boiling water or the surface of the Sun?",
        "a": "The surface of the Sun",
        "options": ["Boiling water", "The surface of the Sun", "They're similar", "Depends on the cup"],
        "subject": "science",
    },
    {
        "q": "Which is heavier: a litre of water or a litre of ice?",
        "a": "A litre of water",
        "options": ["Water", "Ice", "They're equal", "Depends on temperature"],
        "subject": "science",
    },
    {
        "q": "What happens to the boiling point of water at higher altitude?",
        "a": "It decreases",
        "options": ["It increases", "It decreases", "It stays the same", "It disappears"],
        "subject": "science",
    },
    {
        "q": "Can sound travel through the vacuum of space?",
        "a": "No, sound needs a medium",
        "options": ["Yes, it travels faster", "No, sound needs a medium", "Only at night", "Only with light"],
        "subject": "science",
    },
    {
        "q": "What color is a mirror?",
        "a": "It has no color of its own",
        "options": ["Silver", "White", "It has no color of its own", "Grey"],
        "subject": "science",
    },
    {
        "q": "How long does it take for sunlight to reach Earth?",
        "a": "About 8 minutes",
        "options": ["About 1 second", "About 8 minutes", "About 1 hour", "Instantly"],
        "subject": "science",
    },
    {
        "q": "Is a tomato a fruit or a vegetable?",
        "a": "It's a fruit botanically",
        "options": ["A vegetable", "A fruit botanically", "Both", "Neither"],
        "subject": "science",
    },
    {
        "q": "Which blood type is known as the universal donor?",
        "a": "O negative",
        "options": ["AB positive", "O negative", "A positive", "B negative"],
        "subject": "science",
    },
    {
        "q": "How many bones does an adult human have?",
        "a": "206",
        "options": ["206", "212", "300", "150"],
        "subject": "science",
    },
    {
        "q": "How many hearts does an octopus have?",
        "a": "3",
        "options": ["1", "2", "3", "8"],
        "subject": "science",
    },
    {
        "q": "Which is the only mammal that cannot jump?",
        "a": "Elephant",
        "options": ["Hippopotamus", "Elephant", "Rhino", "Giraffe"],
        "subject": "science",
    },
    {
        "q": "What is the only metal that is liquid at room temperature?",
        "a": "Mercury",
        "options": ["Gold", "Mercury", "Silver", "Lead"],
        "subject": "science",
    },
]


# ============================================================
# HELPERS
# ============================================================
def _today_seed(today=None):
    """Deterministic seed for today (integer day count)."""
    d = today or date.today()
    return d.toordinal()


def get_daily_question(today=None, shuffle_options=True):
    """
    Return today's question dict:
      {
        "q":         question text,
        "a":         correct answer,
        "options":   (possibly shuffled) list of options,
        "subject":   category,
        "q_index":   raw index in QUIZ_BANK (for debugging),
      }

    Rotation: cycles through QUIZ_BANK every N days.
    If shuffle_options=True, option order changes each day
    but stays consistent for all users on the same day.
    """
    d = today or date.today()
    seed = _today_seed(d)

    idx = seed % len(QUIZ_BANK)
    base = QUIZ_BANK[idx]

    options = list(base["options"])
    if shuffle_options:
        rng = random.Random(seed)  # deterministic per day
        rng.shuffle(options)

    return {
        "q": base["q"],
        "a": base["a"],
        "options": options,
        "subject": base.get("subject", "general"),
        "q_index": idx,
    }


def is_correct_answer(question_dict, user_answer):
    """Exact match (case-insensitive, whitespace-trimmed)."""
    if user_answer is None:
        return False
    correct = (question_dict.get("a") or "").strip().lower()
    given = str(user_answer).strip().lower()
    return correct == given


def total_questions():
    """How many questions in the bank."""
    return len(QUIZ_BANK)


def days_until_repeat():
    """How many days until the cycle repeats."""
    return len(QUIZ_BANK)


def get_questions_by_subject(subject):
    """Return all questions for a given subject."""
    return [q for q in QUIZ_BANK if q.get("subject") == subject]


def list_subjects():
    """Return list of unique subjects."""
    return sorted({q.get("subject", "general") for q in QUIZ_BANK})


def get_question_stats():
    """Return a dict of subject → count."""
    stats = {}
    for q in QUIZ_BANK:
        s = q.get("subject", "general")
        stats[s] = stats.get(s, 0) + 1
    return stats
