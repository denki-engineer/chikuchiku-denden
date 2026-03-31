# ⚡ Battery Cost Optimization Simulator

[日本語版はこちら](README_ja.md)

Simulates annual electricity cost using 30-minute interval data (17,520 points)
and evaluates battery operation strategies for demand reduction.

👉 Designed for real-world industrial energy optimization

---

## 🖼 Screenshots

### UI (STEP5)

![UI](assets/ui_step5.png)

### Before / After Comparison

![Graph](assets/graph_before_after.png)

---

## 📊 Scale of Computation

* 17,520 time-series data points (30min × 1 year)
* 1,152 tariff unit prices
* Multi-mode battery scheduling simulation

---

## 🔋 Features

* Battery operation modes:

  * Fixed
  * Grid target (demand shaving)
  * SoC target

* Monthly & annual cost evaluation

* Representative week extraction

* CSV / ZIP project import & export

---

## 🧠 Technical Highlights

* NumPy-based vectorized computation
* Engine/UI separation architecture
* Constraint-based simulation
* Cached execution for fast iteration (~0.3s/year)

---

## 📈 What This Solves

Manual analysis requires:

* Handling tens of thousands of data points
* Applying complex tariff rules
* Iterating multiple operation strategies

👉 This tool automates the entire process

---

## 🔒 Data Integrity

* No proprietary or confidential data used
* Based on public information and general engineering principles
* Fully reproducible using synthetic datasets

---

## ⚠️ Assumptions

* No renewable generation modeled
* No battery efficiency / degradation
* No additional charges (e.g., renewable surcharge)
* Results are approximate

---

## ▶️ How to Run

```
pip install -r requirements.txt
streamlit run app.py
```

---

## 💡 Concept

This is not a theoretical model,
but a practical simulation tool designed for decision-making.

---

## 👤 Author

Electrical engineering × Software × Energy optimization
