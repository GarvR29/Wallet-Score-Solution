Aave V2 Wallet Credit Scoring

This repository contains a Python script (score_wallets.py) designed to assign a credit score to Aave V2 protocol wallets based on their historical transaction behavior. The model aims to differentiate between reliable/responsible usage and risky/exploitative patterns, assigning scores between 0 and 1000.

1. Problem Statement
The challenge is to develop a robust machine learning model that assigns a credit score (0-1000) to each wallet based solely on historical transaction behavior from the Aave V2 protocol. Higher scores indicate reliable and responsible usage; lower scores reflect risky, bot-like, or exploitative behavior.

2. Data Source
The script processes transaction-level data from the Aave V2 protocol. This data is provided in a JSON file (user-wallet-transactions.json).

Download the data:
Raw JSON file (~87MB): https://drive.google.com/file/d/1ISFbAXxadMrt7Zl96rmzzZmEKZnyW7FS/view?usp=sharing
Compressed ZIP file (~10MB): https://drive.google.com/file/d/14ceBCLQ-BTcydDrFJauVA_PKAZ7VtDor/view?usp=sharing

Note: Please download the user-wallet-transactions.json file and place it in the same directory as score_wallets.py for the script to run successfully
3. Method Chosen: Feature Engineering with Weighted Additive Scoring
The approach to assigning credit scores involves a two-main step process: extensive feature engineering from raw transaction data, followed by a weighted additive scoring model. This method was chosen for its interpretability and ability to directly link specific behavioral patterns to the resulting credit score.

Interpretability: Each feature's contribution to the final score is explicit through its weight, making the model's logic transparent.

Flexibility: The weights can be easily adjusted and tuned based on domain expertise or further analysis of what constitutes "responsible" versus "risky" behavior.

Scalability: The feature engineering process is designed to handle large datasets efficiently using Pandas.

4. Complete Architecture
The solution's architecture is structured into distinct, sequential components:

Data Ingestion and Preprocessing Layer:

Input: user-wallet-transactions.json (raw transaction data).

Functionality:

Loads JSON data into a Pandas DataFrame.

Parses and converts various fields (e.g., _id, timestamp, createdAt, updatedAt) into appropriate data types (e.g., datetime objects, floats).

Extracts and normalizes numerical values from nested JSON structures (e.g., amount, assetPriceUSD from actionData).

Calculates amountUSD for all transactions by multiplying amount with assetPriceUSD to provide a standardized value.

Output: A clean, prepared Pandas DataFrame ready for feature engineering.

Feature Engineering Layer:

Input: Preprocessed transaction DataFrame.

Functionality: Aggregates transaction-level data to wallet-level features. These features are designed to capture different facets of a wallet's interaction with the Aave V2 protocol.

Activity Metrics: Total transactions, first/last transaction dates, activity duration, average daily transactions.

Action-Specific Aggregates: Counts of deposits, borrows, repays, redemptions, and liquidations. Sums of USD values for these actions.

Behavioral Ratios & Flags:

net_flow_usd: (Total Deposits USD - Total Redeems USD) - indicates net capital flow.

borrow_to_repay_ratio: (Total Borrow USD / Total Repay USD) - indicates debt management efficiency, capped to prevent extreme outliers.

liquidation_flag: A binary flag (1 if the wallet has experienced a liquidationcall, 0 otherwise) as a strong indicator of risk.

Output: A DataFrame where each row represents a unique userWallet and its engineered features.

Credit Scoring Model Layer:

Input: Wallet-level features DataFrame.

Functionality:

Feature Scaling: All engineered features are normalized to a 0-1 range using Min-Max scaling. For features that negatively impact the score (e.g., borrow_to_repay_ratio, liquidation_flag), the scaled value is inverted (1 - scaled value) to ensure higher values of the original feature result in a lower score contribution.

Weighted Sum: A raw score is calculated by summing the scaled features, each multiplied by a predefined weight. These weights are set to reflect the relative importance of each behavior in determining creditworthiness (e.g., high deposits and repayments are positively weighted, liquidations are strongly negatively weighted).

Final Score Normalization: The raw scores are then scaled to the final 0-1000 range.

Output: A dictionary mapping userWallet addresses to their calculated credit_score.
5. Processing Flow
The score_wallets.py script executes the following sequence of operations:

Initialization: An instance of the WalletScorer class is created, pointing to the user-wallet-transactions.json file.

Load and Preprocess Data (load_and_preprocess_data method):

The JSON file is read into a Pandas DataFrame.

Necessary data type conversions and initial calculations (like amountUSD) are performed. Error handling is included for file not found or JSON decoding issues.

Engineer Features (engineer_features method):

The preprocessed DataFrame is grouped by userWallet.

Aggregate functions are applied to calculate all the defined features (counts, sums, ratios, duration, flags).

The resulting feature DataFrame is stored within the WalletScorer instance.

Calculate Scores (calculate_scores method):

The engineered features are scaled (Min-Max and inversion for negative indicators).

A raw score is computed for each wallet using the predefined weights.

The raw scores are normalized to the 0-1000 range.

The final credit_score is added as a new column to the wallet features DataFrame, and a dictionary of wallet-score pairs is created.

Output and Analysis (in if __name__ == "__main__": block):

A sample of the top 10 wallet scores is printed to the console.

The distribution of scores across 100-point ranges is displayed.

Insights into the characteristics of the top 5 highest-scoring and bottom 5 lowest-scoring wallets are printed, highlighting the key features driving their scores.

