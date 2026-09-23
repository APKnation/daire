"""
Standalone script to use the trained credit risk prediction model.
This shows you how to save the model and load it later for production use.
"""

import pandas as pd
import joblib
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, classification_report

# First, train the model and save it (this only needs to be done once)
def train_and_save_model():
    # Load the dataset
    lending_data = pd.read_csv(Path("Resources/lending_data.csv"))
    
    # Prepare features and labels
    y = lending_data["loan_status"]
    X = lending_data.drop(columns="loan_status")
    
    # Split the data
    X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=1, stratify=y)
    
    # Train the model
    LR_model = LogisticRegression(random_state=1)
    LR_model.fit(X_train, y_train)
    
    # Evaluate
    predictions = LR_model.predict(X_test)
    print("Model Evaluation:")
    print(f"Accuracy: {LR_model.score(X_test, y_test):.2%}")
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, predictions))
    print("\nClassification Report:")
    print(classification_report(y_test, predictions))
    
    # Save the model to a file (can be loaded later without retraining)
    joblib.dump(LR_model, 'credit_risk_model.joblib')
    print("\nModel saved as 'credit_risk_model.joblib'")
    
    return LR_model

# Load the saved model and use it for predictions
def load_model_and_predict():
    # Load the saved model
    if Path('credit_risk_model.joblib').exists():
        LR_model = joblib.load('credit_risk_model.joblib')
        print("Loaded saved model successfully!")
    else:
        print("No saved model found, training new model...")
        LR_model = train_and_save_model()
    
    # Prediction function
    def predict_loan_risk(loan_size, interest_rate, borrower_income, debt_to_income, 
                          num_of_accounts, derogatory_marks, total_debt):
        """
        Predict if a loan application is high-risk (1) or healthy (0).
        """
        new_application = pd.DataFrame({
            'loan_size': [loan_size],
            'interest_rate': [interest_rate],
            'borrower_income': [borrower_income],
            'debt_to_income': [debt_to_income],
            'num_of_accounts': [num_of_accounts],
            'derogatory_marks': [derogatory_marks],
            'total_debt': [total_debt]
        })
        
        prediction = LR_model.predict(new_application)[0]
        probabilities = LR_model.predict_proba(new_application)[0]
        confidence = probabilities[prediction]
        
        return prediction, confidence
    
    # Test with new applications
    print("\n--- Testing New Loan Applications ---")
    
    # Example 1: Low risk application
    pred1, conf1 = predict_loan_risk(
        loan_size=10000, interest_rate=7.5, borrower_income=50000,
        debt_to_income=0.3, num_of_accounts=4, derogatory_marks=0, total_debt=15000
    )
    print(f"\nApplication 1:")
    print(f"Status: {'✅ HEALTHY (low risk)' if pred1 == 0 else '⚠️ HIGH RISK'}")
    print(f"Confidence: {conf1:.2%}")
    
    # Example 2: High risk application
    pred2, conf2 = predict_loan_risk(
        loan_size=20000, interest_rate=12.5, borrower_income=45000,
        debt_to_income=0.85, num_of_accounts=2, derogatory_marks=3, total_debt=38000
    )
    print(f"\nApplication 2:")
    print(f"Status: {'✅ HEALTHY (low risk)' if pred2 == 0 else '⚠️ HIGH RISK'}")
    print(f"Confidence: {conf2:.2%}")
    
    # Example 3: Another real application from the dataset (actual status=0)
    pred3, conf3 = predict_loan_risk(
        loan_size=10700, interest_rate=7.672, borrower_income=52800,
        debt_to_income=0.4318, num_of_accounts=5, derogatory_marks=1, total_debt=22800
    )
    print(f"\nApplication 3 (from original dataset, actual status=0):")
    print(f"Status: {'✅ HEALTHY (low risk)' if pred3 == 0 else '⚠️ HIGH RISK'}")
    print(f"Confidence: {conf3:.4%}")  # Show more decimal places
    
    # Example 4: BORDERLINE CASE - this will have lower confidence!
    pred4, conf4 = predict_loan_risk(
        loan_size=15000, interest_rate=10.0, borrower_income=48000,
        debt_to_income=0.55, num_of_accounts=3, derogatory_marks=1, total_debt=26400
    )
    print(f"\nApplication 4 (BORDERLINE case):")
    print(f"Status: {'✅ HEALTHY (low risk)' if pred4 == 0 else '⚠️ HIGH RISK'}")
    print(f"Confidence: {conf4:.4%}")  # Show raw probability with 4 decimal places
    
    # Let's also print ALL probabilities to see what's really happening
    print("\n--- Debug: Raw probabilities for all tests ---")
    # Add debug function to show both probabilities
    def debug_probabilities(*args, **kwargs):
        new_application = pd.DataFrame({
            'loan_size': [args[0]],
            'interest_rate': [args[1]],
            'borrower_income': [args[2]],
            'debt_to_income': [args[3]],
            'num_of_accounts': [args[4]],
            'derogatory_marks': [args[5]],
            'total_debt': [args[6]]
        })
        probs = LR_model.predict_proba(new_application)[0]
        print(f"P(healthy=0): {probs[0]:.6f}, P(high-risk=1): {probs[1]:.6f}")
    
    print("App1 (clear healthy):")
    debug_probabilities(10000,7.5,50000,0.3,4,0,15000)
    print("App2 (clear high-risk):")
    debug_probabilities(20000,12.5,45000,0.85,2,3,38000)
    print("App4 (borderline):")
    debug_probabilities(15000,10.0,48000,0.55,3,1,26400)

if __name__ == "__main__":
    load_model_and_predict()