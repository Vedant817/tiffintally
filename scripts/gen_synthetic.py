"""
Generate rich synthetic WhatsApp tiffin order dataset in Hinglish, English, and Hindi.
Expanded with realistic variations: cancellations, multi-person, modifications,
payments, chitchat, pauses, typos, delivery timings, and lexical Hindi number words ("ek", "do", "teen", "chaar").
"""

import json
import random
from pathlib import Path
from typing import Any, Dict, List

SEED = 42
TARGET_COUNT = 1250
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
    "Nikhil",
    "Bhavna",
    "Karthik",
    "Swati",
    "Varun",
    "Aishwarya",
    "Manish",
    "Pallavi",
    "Harsh",
    "Ritu",
    "Abhishek",
    "Kriti",
    "Mohit",
    "Sunita",
    "Chirag",
    "Preeti",
    "Rajesh",
    "Ishita",
    "Vivek",
    "Geeta",
    "Tarun",
    "Monika",
    "Sameer",
    "Alok",
    "Anjali",
    "Naveen",
    "Renu",
    "Devendra",
]

FRIENDS = ["Priya", "Amit", "Rahul", "Sneha", "Rohan", "Neha", "Vikas", "Anjali", "Tanvi", "Saurabh"]

QTY_WORDS = {
    1: ["1", "ek", "one"],
    2: ["2", "do", "two"],
    3: ["3", "teen", "three"],
    4: ["4", "chaar", "four"],
}

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
    ("kal lunch teen thali", "lunch", 3, ["thali"], [], "new"),
    ("teen dinner box please", "dinner", 3, ["thali"], [], "new"),
    ("do lunch aur ek dinner", "lunch", 2, ["thali"], [], "new"),
    ("kal se daily lunch shuru kar do please {qty} plate", "lunch", "{qty}", ["thali"], [], "new"),
    ("pack {qty} meals for tomorrow lunch", "lunch", "{qty}", ["thali"], [], "new"),
    ("send regular tiffin tomorrow {qty}", "lunch", "{qty}", ["thali"], [], "new"),
]

# 2. Dietary Modifications & Substitutions
TEMPLATES_MODS = [
    ("kal lunch {qty}, bina pyaaz ke", "lunch", "{qty}", ["thali"], ["no onion"], "new"),
    ("kal raat ka dinner {qty} jain thali", "dinner", "{qty}", ["thali"], ["jain"], "new"),
    ("kal lunch 1, roti nahi sirf rice dena", "lunch", 1, ["thali"], ["roti nahi rice"], "new"),
    ("dinner 1, no garlic no onion", "dinner", 1, ["thali"], ["no onion", "no garlic"], "new"),
    ("kal lunch {qty}, kam teekha banana", "lunch", "{qty}", ["thali"], ["less spicy"], "new"),
    ("lunch 1, extra rice please aunty", "lunch", 1, ["thali"], ["extra rice"], "new"),
    ("kal dinner {qty}, less oily please stomach upset hai", "dinner", "{qty}", ["thali"], ["less oily"], "new"),
    ("kal lunch 1, dal zyada sabzi kam", "lunch", 1, ["thali"], ["dal zyada", "sabzi kam"], "new"),
    ("kal lunch 2, ek bina pyaaz ka", "lunch", 2, ["thali"], ["no onion"], "new"),
    ("1 thali lunch, replace curd with extra sabzi", "lunch", 1, ["thali"], ["no curd", "extra sabzi"], "new"),
    ("bina pyaaz ke {qty} thali bhejo lunch me", "lunch", "{qty}", ["thali"], ["no onion"], "new"),
    ("bina pyaaz ke {qty} tiffin dinner me", "dinner", "{qty}", ["thali"], ["no onion"], "new"),
    ("bina pyaaz {qty} lunch box please", "lunch", "{qty}", ["thali"], ["no onion"], "new"),
    ("pyaaz mat dalna kal ke {qty} dinner me", "dinner", "{qty}", ["thali"], ["no onion"], "new"),
    ("bina pyaaz ke {qty} plate bhejo kal dopahar", "lunch", "{qty}", ["thali"], ["no onion"], "new"),
    ("aunty kal bina pyaaz ke {qty} dabba bhej dena", "lunch", "{qty}", ["thali"], ["no onion"], "new"),
    ("bina lehsun pyaaz {qty} thali kal lunch", "lunch", "{qty}", ["thali"], ["no onion", "no garlic"], "new"),
    ("bina lehsun pyaaz ke {qty} thali dinner", "dinner", "{qty}", ["thali"], ["no onion", "no garlic"], "new"),
    ("jain khana {qty} plate kal dinner", "dinner", "{qty}", ["thali"], ["jain"], "new"),
    ("jain thali {qty} plate lunch tomorrow", "lunch", "{qty}", ["thali"], ["jain"], "new"),
    ("kam teekha {qty} lunch bhej dena", "lunch", "{qty}", ["thali"], ["less spicy"], "new"),
    ("kam mirchi {qty} thali lunch aunty", "lunch", "{qty}", ["thali"], ["less spicy"], "new"),
    ("less spicy {qty} dinner box", "dinner", "{qty}", ["thali"], ["less spicy"], "new"),
    ("bina mirchi ke {qty} dabba dinner", "dinner", "{qty}", ["thali"], ["no chili"], "new"),
    ("bina mirchi wala {qty} dabba kal lunch", "lunch", "{qty}", ["thali"], ["no chili"], "new"),
    ("roti nahi sirf rice dena {qty} plate lunch", "lunch", "{qty}", ["thali"], ["roti nahi rice"], "new"),
    ("oil kam rakhna {qty} thali dinner me", "dinner", "{qty}", ["thali"], ["less oily"], "new"),
    ("bina pyaaz ke teen thali bhejo lunch me", "lunch", 3, ["thali"], ["no onion"], "new"),
    ("less spicy teen dinner box", "dinner", 3, ["thali"], ["less spicy"], "new"),
    ("kam teekha do thali lunch me", "lunch", 2, ["thali"], ["less spicy"], "new"),
    ("Please give curd instead of kheer tomorrow lunch", "lunch", 1, ["thali"], ["curd instead of kheer"], "new"),
    ("lunch 1 thali, strictly Jain no root vegetables", "lunch", 1, ["thali"], ["jain no root vegetables"], "new"),
    ("tomorrow lunch 2, 1 normal 1 without dal", "lunch", 2, ["thali"], ["one without dal"], "new"),
    ("Aunty lunch me 4 roti dena rice mat bhejna", "lunch", 1, ["thali"], ["4 roti no rice"], "new"),
    ("dinner 1 plate, can you send extra pickle?", "dinner", 1, ["thali"], ["extra pickle"], "new"),
    ("kal lunch 1 thali, less oil in sabzi please", "lunch", 1, ["thali"], ["less oil"], "new"),
    ("Aunty kal afternoon 2 meals, but 1 meal no rice only rotis please", "lunch", 2, ["thali"], ["one no rice only rotis"], "new"),
]

# 3. Delivery Timings & Clock References (crucial for not confusing time with qty!)
TEMPLATES_DELIVERY_TIMINGS = [
    ("Send dinner tonight by 8:30 pm sharp, 1 thali less spicy", "dinner", 1, ["thali"], ["less spicy"], "new"),
    ("1 plate lunch tomorrow, please deliver by 1:00 PM", "lunch", 1, ["thali"], [], "new"),
    ("dinner 2 thali tonight around 9 pm", "dinner", 2, ["thali"], [], "new"),
    ("lunch at 12:30 pm sharp, 1 dabba", "lunch", 1, ["thali"], [], "new"),
    ("pack 1 dinner, will pick up at 8 pm", "dinner", 1, ["thali"], [], "new"),
    ("lunch 2 plates please deliver before 1:30 PM", "lunch", 2, ["thali"], [], "new"),
    ("kal lunch 1 thali 12 pm tak bhej dena", "lunch", 1, ["thali"], [], "new"),
]

# 4. Cancels
TEMPLATES_CANCELS = [
    ("kal lunch cancel", "lunch", 0, [], [], "cancel"),
    ("aunty kal lunch nahi chahiye, cancel kar do", "lunch", 0, [], [], "cancel"),
    ("dinner skip tonight", "dinner", 0, [], [], "cancel"),
    ("kal dinner cancel please office party hai", "dinner", 0, [], [], "cancel"),
    ("cancel tomorrow's lunch", "lunch", 0, [], [], "cancel"),
    ("aaj raat ka dinner nahi hoga, cancel", "dinner", 0, [], [], "cancel"),
    ("please cancel lunch tomorrow", "lunch", 0, [], [], "cancel"),
    ("kal lunch mat bhejna aunty", "lunch", 0, [], [], "cancel"),
    ("kal lunch cancel aunty, team lunch hai office me", "lunch", 0, [], [], "cancel"),
    ("kal lunch cancel kar do aunty, team outing hai", "lunch", 0, [], [], "cancel"),
    ("Aunty please cancel dinner tonight, fever aa gaya hai", "dinner", 0, [], [], "cancel"),
    ("Aunty dinner cancel kar dijiye aaj ka", "dinner", 0, [], [], "cancel"),
    ("cancel kal lunch", "lunch", 0, [], [], "cancel"),
    ("kal lunch skip please", "lunch", 0, [], [], "cancel"),
    ("cancel dinner today", "dinner", 0, [], [], "cancel"),
]

# 5. Changes / Updates
TEMPLATES_CHANGES = [
    ("kal lunch 1 nahi 2 kar dena", "lunch", 2, ["thali"], [], "change"),
    ("earlier ordered 1, make it 3 thalis for dinner", "dinner", 3, ["thali"], [], "change"),
    ("change dinner from 2 to 1 thali", "dinner", 1, ["thali"], [], "change"),
    ("aunty dopahar ka dabba cancel, shaam ko 2 kar dena", "dinner", 2, ["thali"], [], "change"),
    ("change lunch to dinner tomorrow", "dinner", 1, ["thali"], [], "change"),
    ("Earlier I asked for 1 dinner, please change it to 3 thalis, friends are coming over", "dinner", 3, ["thali"], [], "change"),
    ("kal lunch cancel, dinner 2 plates", "dinner", 2, ["thali"], [], "change"),
    ("kal lunch 2 nahi 1 hi bhejna, dost bahar gaya", "lunch", 1, ["thali"], [], "change"),
    ("change 1 to 2 thalis for dinner tonight", "dinner", 2, ["thali"], [], "change"),
]

# 6. Pauses / Vacations
TEMPLATES_PAUSES = [
    ("Sunday off please, going home for weekend", "both", 0, [], [], "pause"),
    ("pause my tiffin from tomorrow till Sunday", "both", 0, [], [], "pause"),
    ("leaving for native place, 3 days pause", "both", 0, [], [], "pause"),
    ("weekend off as usual aunty", "both", 0, [], [], "pause"),
    ("stop tiffin for next 2 days", "both", 0, [], [], "pause"),
    ("going home for Diwali, Sunday se next Thursday tak band rakhna", "both", 0, [], [], "pause"),
    ("Sunday off please, don't deliver lunch or dinner", "both", 0, [], [], "pause"),
    ("no tiffin for next 3 days, project submission chal raha hai", "both", 0, [], [], "pause"),
    ("pause tiffin for weekend Saturday and Sunday", "both", 0, [], [], "pause"),
]

# 7. Multi-person / Roommate Orders
TEMPLATES_MULTI_PERSON = [
    ("kal lunch ek plate aur roommate {friend} ke liye bhi ek", "lunch", 1, ["thali"], [], "new"),
    ("Meri roommate {friend} ke liye bhi ek lunch add kar dena", "lunch", 1, ["thali"], [], "new"),
    ("dono {friend} and me will take dinner tonight", "dinner", 2, ["thali"], [], "new"),
    ("{friend} ka bhi ek dinner pack kar do saath me", "dinner", 1, ["thali"], [], "new"),
    ("roommate {friend} ka lunch cancel, mera regular bhejna", "lunch", 1, ["thali"], [], "new"),
    ("Aunty kal lunch 1 plate. Aur meri roommate {friend} ke liye bhi ek lunch add kar dena", "lunch", 2, ["thali"], [], "new"),
    ("Add 1 dinner for my cousin {friend} as well", "dinner", 1, ["thali"], [], "new"),
    ("add one more plate for {friend} dinner tonight", "dinner", 1, ["thali"], [], "new"),
]

# 8. Payments & Dues
TEMPLATES_PAYMENTS = [
    ("500 GPay kiya aunty check kar lo", "unspecified", 0, [], [], "payment", 500.0),
    ("paid 1500 via PhonePe for this week", "unspecified", 0, [], [], "payment", 1500.0),
    ("1000 transfer kar diya Paytm pe", "unspecified", 0, [], [], "payment", 1000.0),
    ("dues clear kar diye 2000 Google Pay se", "unspecified", 0, [], [], "payment", 2000.0),
    ("Aunty 800 bhej diye account me", "unspecified", 0, [], [], "payment", 800.0),
    ("Aunty ₹2100 transfer kiya GPay pe, last 2 weeks ka", "unspecified", 0, [], [], "payment", 2100.0),
    ("GPay done 1500", "unspecified", 0, [], [], "payment", 1500.0),
    ("paid ₹800 on phonepe just now", "unspecified", 0, [], [], "payment", 800.0),
    ("sending ₹3200 for full month tomorrow morning aunty", "unspecified", 0, [], [], "payment", 3200.0),
    ("₹1600 transferred via Paytm", "unspecified", 0, [], [], "payment", 1600.0),
    ("paid dues 2400 on gpay", "unspecified", 0, [], [], "payment", 2400.0),
]

# 9. Chit-Chat & Gratitude (action=none)
TEMPLATES_CHITCHAT = [
    ("khana bahut tasty tha aunty! thank you!", "unspecified", 0, [], [], "none"),
    ("today's paneer was amazing aunty ji", "unspecified", 0, [], [], "none"),
    ("gulab jamun bahut mast the", "unspecified", 0, [], [], "none"),
    ("aunty menu kya hai kal ka?", "unspecified", 0, [], [], "none"),
    ("happy diwali aunty to you and family!", "unspecified", 0, [], [], "none"),
    ("thank you aunty, khana bahut mast tha!", "unspecified", 0, [], [], "none"),
    ("Aaj ki bhindi fry bahut badiya thi aunty maza aa gaya!", "unspecified", 0, [], [], "none"),
    ("Good night aunty, kal milenge", "unspecified", 0, [], [], "none"),
    ("Aunty menu kya hai kal lunch ka?", "unspecified", 0, [], [], "none"),
    ("Gulab jamun was so sweet thank you aunty", "unspecified", 0, [], [], "none"),
    ("Super tasty khana! Thank you so much aunty", "unspecified", 0, [], [], "none"),
]

# 10. Typos & Informal Slang
TEMPLATES_TYPOS = [
    ("kl lnch 1 plzz", "lunch", 1, ["thali"], [], "new"),
    ("tomrw dinr cncl", "dinner", 0, [], [], "cancel"),
    ("aaj rat ko 2 dabbe", "dinner", 2, ["thali"], [], "new"),
    ("lunc 2 dabba bina pyaz", "lunch", 2, ["thali"], ["no onion"], "new"),
    ("dinr 1 no spic", "dinner", 1, ["thali"], ["less spicy"], "new"),
    ("kl lunc 1 plae", "lunch", 1, ["thali"], [], "new"),
    ("tomrw lunh 2 thli pls", "lunch", 2, ["thali"], [], "new"),
    ("dinnr cancl", "dinner", 0, [], [], "cancel"),
]

# 11. Devanagari Hindi
TEMPLATES_DEVANAGARI = [
    ("कल दो थाली", "lunch", 2, ["thali"], [], "new"),
    ("कल दोपहर का खाना एक प्लेट", "lunch", 1, ["thali"], [], "new"),
    ("आज रात का टिफिन कैंसिल कर दीजिए", "dinner", 0, [], [], "cancel"),
    ("कल लंच नहीं चाहिए आंटी", "lunch", 0, [], [], "cancel"),
    ("कल रात को दो टिफिन भेजना, बिना प्याज के", "dinner", 2, ["thali"], ["bina pyaaz"], "new"),
    ("खाना बहुत स्वादिष्ट था धन्यवाद", "unspecified", 0, [], [], "none"),
    ("कल दो थाली दोपहर को भेजना", "lunch", 2, ["thali"], [], "new"),
    ("कल रात का खाना कैंसिल", "dinner", 0, [], [], "cancel"),
    ("कल दोपहर एक थाली, बिना मिर्ची की", "lunch", 1, ["thali"], ["bina mirchi"], "new"),
    ("आज रात १ डब्बा", "dinner", 1, ["thali"], [], "new"),
]


def generate_synthetic_dataset(
    target_count: int = TARGET_COUNT, seed: int = SEED
) -> List[Dict[str, Any]]:
    random.seed(seed)
    records = []
    idx = 1

    categories = [
        ("standard", TEMPLATES_NEW_ORDER, 220),
        ("mods", TEMPLATES_MODS, 320),
        ("timings", TEMPLATES_DELIVERY_TIMINGS, 100),
        ("cancels", TEMPLATES_CANCELS, 140),
        ("changes", TEMPLATES_CHANGES, 90),
        ("pauses", TEMPLATES_PAUSES, 70),
        ("multi", TEMPLATES_MULTI_PERSON, 80),
        ("payments", TEMPLATES_PAYMENTS, 80),
        ("chitchat", TEMPLATES_CHITCHAT, 60),
        ("typos", TEMPLATES_TYPOS, 50),
        ("devanagari", TEMPLATES_DEVANAGARI, 60),
    ]

    for _cat_name, templates, count in categories:
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
            if isinstance(actual_qty, int) and actual_qty in QTY_WORDS:
                candidates = QTY_WORDS[actual_qty]
                chosen_qty_str = random.choice(candidates) if random.random() < 0.65 else str(actual_qty)
            else:
                chosen_qty_str = str(actual_qty)

            text = text_pattern.replace("{qty}", chosen_qty_str)

            sec_customer = None
            if "{friend}" in text:
                sec_friend = random.choice([f for f in FRIENDS if f != sender])
                text = text.replace("{friend}", sec_friend)
                sec_customer = sec_friend

            payment_note = f"GPay/UPI transfer of {payment_amount}" if payment_amount else None

            record = {
                "id": f"syn_{idx:04d}",
                "sender": sender,
                "raw_text": text,
                "gold": {
                    "customer": sender,
                    "date": "tomorrow",
                    "meal": meal,
                    "qty": actual_qty if isinstance(actual_qty, int) else 1,
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

    print(f"Wrote {len(train_set)} to {train_path} and {len(test_set)} to {test_path}")


if __name__ == "__main__":
    main()
