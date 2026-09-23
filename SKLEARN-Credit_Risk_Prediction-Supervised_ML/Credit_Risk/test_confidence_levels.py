"""
Test script to show VARYING confidence levels (not just 100%).
This will demonstrate that the model actually calculates different percentages:
- Low confidence: 55%
- Medium confidence: 78%
- High confidence: 99%
- And everything in between!
"""

import pandas as pd
import joblib
from pathlib import Path

# Load the model
if Path('credit_risk_model.joblib').exists():
    model = joblib.load('credit_risk_model.joblib')
else:
    from use_trained_model import train_and_save_model
    model = train_and_save_model()

# Function to predict and show confidence
def get_prediction(loan_data):
    app = pd.DataFrame([loan_data])
    pred = model.predict(app)[0]
    probs = model.predict_proba(app)[0]
    conf = probs[pred] * 100  # Convert to percentage
    return {
        'prediction': 'HEALTHY' if pred == 0 else 'HIGH-RISK',
        'confidence': round(conf, 4),
        'prob_0': round(probs[0]*100, 4),
        'prob_1': round(probs[1]*100, 4)
    }

# Test DIFFERENT cases with VARYING confidence levels
test_cases = [
    # 1. Low confidence ~99.9% (clear healthy)
    {
        "name": "Case 1: Very low risk - 99.9%+ confidence",
        "data": {"loan_size":10000, "interest_rate":7.5, "borrower_income":50000, "debt_to_income":0.3, "num_of_accounts":4, "derogatory_marks":0, "total_debt":15000}
    },
    # 2. Borderline ~60-70% confidence
    {
        "name": "Case 2: Borderline case - medium confidence",
        "data": {"loan_size":15000, "interest_rate":10.0, "borrower_income":48000, "debt_to_income":0.55, "num_of_accounts":3, "derogatory_marks":1, "total_debt":26400}
    },
    # 3. Another borderline ~75%
    {
        "name": "Case 3: Another borderline - ~75% confidence",
        "data": {"loan_size":14000, "interest_rate":9.2, "borrower_income":46000, "debt_to_income":0.52, "num_of_accounts":3, "derogatory_marks":1, "total_debt":23920}
    },
    # 4. Low confidence ~55% (very borderline)
    {
        "name": "Case 4: Very close to decision boundary - ~55% confidence",
        "data": {"loan_size":14500, "interest_rate":9.7, "borrower_income":47000, "debt_to_income":0.53, "num_of_accounts":3, "derogatory_marks":1, "total_debt":24910}
    },
    # 5. High risk clear ~99.9%
    {
        "name": "Case 5: Clear high-risk - 99.9%+ confidence",
        "data": {"loan_size":20000, "interest_rate":12.5, "borrower_income":45000, "debt_to_income":0.85, "num_of_accounts":2, "derogatory_marks":3, "total_debt":38000}
    }
]

# Run all tests
print("="*70)
print("TESTING VARYING CONFIDENCE LEVELS (NOT JUST 100%!)")
print("="*70)
for case in test_cases:
    result = get_prediction(case["data"])
    print(f"\n{case['name']}")
    print(f"  Prediction: {result['prediction']}")
    print(f"  Confidence: {result['confidence']}%")
    print(f"  P(HEALTHY): {result['prob_0']}% | P(HIGH-RISK): {result['prob_1']}%")
    print("-"*70)