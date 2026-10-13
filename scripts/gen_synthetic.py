"""
Synthetic Dataset Generator for Tiffin WhatsApp Orders.
Generates >=600 diverse Hinglish, English, typo-ridden, and Devanagari messages with gold labels.
Seeded and 100% reproducible.
"""

import json
import random
from pathlib import Path
from typing import Any, Dict, List

SEED = 42
TARGET_COUNT = 650

OUTPUT_DIR = Path("data/synthetic")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SENDERS = [
    "Ravi",
    "Priya",
    "Amit",
    "Sneha",
    "Karan",
    "Ananya",
    "Vikram",
    "Neha",
    "Rohan",
    "Pooja",
    "Rahul",
    "Divya",
    "Siddharth",
    "Meera",
    "Aditya",
    "Kavita",
    "Deepak",
    "Tanvi",
    "Gaurav",
    "Simran",
    "Arjun",
    "Shreya",
]

FRIENDS = ["Priya", "Amit", "Rahul", "Sneha", "Rohan", "Neha", "Vikas", "Anjali"]

# 1. Standard Orders
TEMPLATES_NEW_ORDER = [
    ("kal lunch {qty}", "lunch", "{qty}", [], [], "new"),
    ("kal lunch {qty} plate", "lunch", "{qty}", ["thali"], [], "new"),
    ("kal lunch {qty} thali bhejo", "lunch", "{qty}", ["thali"], [], "new"),
    ("tomorrow lunch {qty} please", "lunch", "{qty}", ["thali"], [], "new"),
    ("kal dinner {qty}", "dinner", "{qty}", ["thali"], [], "new"),
    ("aaj raat ko {qty} dinner", "dinner", "{qty}", ["thali"], [], "new"),
    ("dinner {qty} thali tonight", "dinner", "{qty}", ["thali"], [], "new"),
    ("lunch aur dinner dono {qty}", "both", "{qty}", ["thali"], [], "new"),
    ("kal dono time {qty} {qty}", "both", "{qty}", ["thali"], [], "new"),
    ("send {qty} lunch box tomorrow", "lunch", "{qty}", ["thali"], [], "new"),
    ("aunty kal {qty} dabba bhej dena", "lunch", "{qty}", ["thali"], [], "new"),
    ("please pack {qty} thali for lunch", "lunch", "{qty}", ["thali"], [], "new"),
]

# 2. Modifications (Dietary / Dish tweaks)
TEMPLATES_MODS = [
    (
        "kal lunch {qty}, roti nahi rice dena",
        "lunch",
        "{qty}",
        ["thali"],
        ["roti nahi rice"],
        "new",
    ),
    (
        "kal dinner 1, no onion no garlic please",
        "dinner",
        1,
        ["thali"],
        ["no onion", "no garlic"],
        "new",
    ),
    ("kal lunch {qty}, kam teekha banana", "lunch", "{qty}", ["thali"], ["kam teekha"], "new"),
    ("lunch 1, extra rice please aunty", "lunch", 1, ["thali"], ["extra rice"], "new"),
    (
        "kal dinner {qty}, less oily please stomach upset hai",
        "dinner",
        "{qty}",
        ["thali"],
        ["less oily"],
        "new",
    ),
    ("kal lunch 1, dal zyada sabzi kam", "lunch", 1, ["thali"], ["dal zyada", "sabzi kam"], "new"),
    ("kal lunch 2, ek bina pyaaz ka", "lunch", 2, ["thali"], ["one without onion"], "new"),
    (
        "1 thali lunch, replace curd with extra sabzi",
        "lunch",
        1,
        ["thali"],
        ["no curd", "extra sabzi"],
        "new",
    ),
]

# 3. Cancels
TEMPLATES_CANCELS = [
    ("kal lunch cancel", "lunch", 0, [], [], "cancel"),
    ("aunty kal lunch nahi chahiye, cancel kar do", "lunch", 0, [], [], "cancel"),
    ("dinner skip tonight", "dinner", 0, [], [], "cancel"),
    ("kal dinner cancel please office party hai", "dinner", 0, [], [], "cancel"),
    ("cancel tomorrow's lunch", "lunch", 0, [], [], "cancel"),
    ("aaj raat ka dinner nahi hoga, cancel", "dinner", 0, [], [], "cancel"),
    ("please cancel lunch tomorrow", "lunch", 0, [], [], "cancel"),
    ("kal lunch mat bhejna aunty", "lunch", 0, [], [], "cancel"),
]

# 4. Changes / Updates
TEMPLATES_CHANGES = [
    ("kal lunch 1 nahi 2 kar dena", "lunch", 2, ["thali"], [], "change"),
    ("earlier ordered 1, make it 3 thalis for dinner", "dinner", 3, ["thali"], [], "change"),
    ("change kal ka lunch to 2 plates", "lunch", 2, ["thali"], [], "change"),
    ("aunty dinner 1 extra add kar do, total 2", "dinner", 2, ["thali"], [], "change"),
    ("lunch quantity update to 3", "lunch", 3, ["thali"], [], "change"),
]

# 5. Pauses (Vacations / Going Home)
TEMPLATES_PAUSES = [
    ("going home for weekend, Sunday off", "both", 0, [], [], "pause"),
    ("next week pura tiffin pause kar do", "both", 0, [], [], "pause"),
    ("aunty 3 din ke liye gaon ja raha hu, no tiffin till Monday", "both", 0, [], [], "pause"),
    ("out of station till 20th, please stop tiffin", "both", 0, [], [], "pause"),
    ("pause tiffin from tomorrow till next Tuesday", "both", 0, [], [], "pause"),
    ("exam holiday next 4 days, tiffin band rakhna", "both", 0, [], [], "pause"),
]

# 6. Multi-Person Orders
TEMPLATES_MULTI_PERSON = [
    ("{friend} ke liye bhi ek lunch add kar do", "lunch", 1, ["thali"], [], "new"),
    ("merath aur {friend} ka kal dinner 2 plate bhejna", "dinner", 2, ["thali"], [], "new"),
    ("add 1 more for my flatmate {friend}", "lunch", 1, ["thali"], [], "new"),
    ("ek mere liye aur ek {friend} ke liye lunch", "lunch", 2, ["thali"], [], "new"),
]

# 7. Payments
TEMPLATES_PAYMENTS = [
    ("₹1500 GPay kiya aunty check kar lo", "unspecified", 0, [], [], "payment", 1500.0),
    ("Paid 2000 on PhonePe for this month", "unspecified", 0, [], [], "payment", 2000.0),
    ("aunty sent 1200 via Paytm", "unspecified", 0, [], [], "payment", 1200.0),
    ("GPay done Rs 1800, screenshot sent", "unspecified", 0, [], [], "payment", 1800.0),
    ("Will pay the ₹2400 dues on Friday aunty pakka", "unspecified", 0, [], [], "payment", 2400.0),
    ("paying 1600 today evening", "unspecified", 0, [], [], "payment", 1600.0),
]

# 8. Chit-Chat / Non-Order Messages
TEMPLATES_CHITCHAT = [
    ("thank you aunty khana mast tha!", "unspecified", 0, [], [], "none"),
    ("Aaj ki dal bahut tasty thi aunty", "unspecified", 0, [], [], "none"),
    ("Good morning aunty ji", "unspecified", 0, [], [], "none"),
    ("Have a great weekend aunty", "unspecified", 0, [], [], "none"),
    ("Ok noted thank you", "unspecified", 0, [], [], "none"),
    ("Sure no problem", "unspecified", 0, [], [], "none"),
    ("Aunty menu kya hai kal ka?", "unspecified", 0, [], [], "none"),
]

# 9. Typos & Slang
TEMPLATES_TYPOS = [
    ("kl lunc 1 plae bhej do", "lunch", 1, ["thali"], [], "new"),
    ("dinnr cancl for tday", "dinner", 0, [], [], "cancel"),
    ("tomrw lunh 2 thli pls", "lunch", 2, ["thali"], [], "new"),
    ("kll dinner nhi chahiy", "dinner", 0, [], [], "cancel"),
    ("lunch 1 plss kam spcy", "lunch", 1, ["thali"], ["kam spicy"], "new"),
    ("ek thali bhejdo kl dopahar", "lunch", 1, ["thali"], [], "new"),
]

# 10. Devanagari Hindi
TEMPLATES_DEVANAGARI = [
    ("कल दो थाली", "lunch", 2, ["thali"], [], "new"),
    ("कल दोपहर का खाना एक प्लेट", "lunch", 1, ["thali"], [], "new"),
    ("आज रात का टिफिन कैंसिल कर दीजिए", "dinner", 0, [], [], "cancel"),
    ("कल लंच नहीं चाहिए आंटी", "lunch", 0, [], [], "cancel"),
    ("कल रात को दो टिफिन भेजना, बिना प्याज के", "dinner", 2, ["thali"], ["bina pyaaz"], "new"),
    ("खाना बहुत स्वादिष्ट था धन्यवाद", "unspecified", 0, [], [], "none"),
]


def generate_synthetic_dataset(
    target_count: int = TARGET_COUNT, seed: int = SEED
) -> List[Dict[str, Any]]:
    random.seed(seed)
    records = []
    idx = 1

    categories = [
        ("standard", TEMPLATES_NEW_ORDER, 180),
        ("mods", TEMPLATES_MODS, 100),
        ("cancels", TEMPLATES_CANCELS, 110),
        ("changes", TEMPLATES_CHANGES, 50),
        ("pauses", TEMPLATES_PAUSES, 40),
        ("multi", TEMPLATES_MULTI_PERSON, 45),
        ("payments", TEMPLATES_PAYMENTS, 45),
        ("chitchat", TEMPLATES_CHITCHAT, 35),
        ("typos", TEMPLATES_TYPOS, 25),
        ("devanagari", TEMPLATES_DEVANAGARI, 25),
    ]

    for cat_name, templates, count in categories:
        for _ in range(count):
            sender = random.choice(SENDERS)
            tmpl = random.choice(templates)
            qty = random.choice([1, 2, 3])

            text_pattern = tmpl[0]
            meal = tmpl[1]
            t_qty = tmpl[2]
            items = list(tmpl[3])
            mods = list(tmpl[4])
            action = tmpl[5]
            payment_amount = tmpl[6] if len(tmpl) > 6 else None

            # Substitutions
            actual_qty = qty if t_qty == "{qty}" else t_qty
            text = text_pattern.replace("{qty}", str(qty))

            sec_customer = None
            if "{friend}" in text:
                sec_friend = random.choice([f for f in FRIENDS if f != sender])
                text = text.replace("{friend}", sec_friend)
                sec_customer = sec_friend

            payment_note = text if action == "payment" else None

            record = {
                "id": f"syn_{idx:04d}",
                "sender": sender,
                "text": text,
                "category": cat_name,
                "is_synthetic": True,
                "gold": {
                    "customer": sender,
                    "date": "tomorrow",
                    "meal": meal,
                    "qty": actual_qty,
                    "items": items,
                    "mods": mods,
                    "action": action,
                    "payment_note": payment_note,
                    "payment_amount": payment_amount,
                    "secondary_customer": sec_customer,
                    "confidence": 1.0,
                },
            }
            records.append(record)
            idx += 1

    # Shuffle with seed
    random.shuffle(records)
    return records


def main():
    records = generate_synthetic_dataset()
    print(f"Generated {len(records)} synthetic messages (Seeded={SEED}).")

    all_path = OUTPUT_DIR / "orders.jsonl"
    with open(all_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 80/20 train/test split
    split_point = int(len(records) * 0.8)
    train_set = records[:split_point]
    test_set = records[split_point:]

    train_path = OUTPUT_DIR / "train.jsonl"
    with open(train_path, "w", encoding="utf-8") as f:
        for r in train_set:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    test_path = OUTPUT_DIR / "test.jsonl"
    with open(test_path, "w", encoding="utf-8") as f:
        for r in test_set:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Split into Train: {len(train_set)} rows, Test: {len(test_set)} rows.")
    print(f"Saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
