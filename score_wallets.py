import json
import pandas as pd
import numpy as np
from datetime import datetime

class WalletScorer:
    def __init__(self, json_file_path="user-wallet-transactions.json"):
        self.json_file_path = json_file_path
        self.df = None
        self.wallet_features = None # Initialize wallet_features
        self.wallet_scores = {}

    def load_and_preprocess_data(self):
        """Loads and preprocesses the transaction data."""
        try:
            with open(self.json_file_path, 'r') as f:
                data = json.load(f)
            self.df = pd.DataFrame(data)
        except FileNotFoundError:
            print(f"Error: JSON file not found at {self.json_file_path}")
            return False
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {self.json_file_path}. Check file format.")
            return False

        # Extract _id
        self.df['_id'] = self.df['_id'].apply(lambda x: x['$oid'])

        # Convert timestamp (it's a number in seconds)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'], unit='s')

        # Convert createdAt and updatedAt (they're dicts)
        def extract_date(x):
            if isinstance(x, dict) and '$date' in x:
                return pd.to_datetime(x['$date'])
            return pd.NaT

        self.df['createdAt'] = self.df['createdAt'].apply(extract_date)
        self.df['updatedAt'] = self.df['updatedAt'].apply(extract_date)

        # Extract amount and assetPriceUSD from actionData and convert to numeric
        self.df['amount'] = self.df['actionData'].apply(
            lambda x: float(x['amount']) if isinstance(x, dict) and 'amount' in x else 0
        )
        self.df['assetSymbol'] = self.df['actionData'].apply(
            lambda x: x.get('assetSymbol', 'UNKNOWN') if isinstance(x, dict) else 'UNKNOWN'
        )
        self.df['assetPriceUSD'] = self.df['actionData'].apply(
            lambda x: float(x['assetPriceUSD']) if isinstance(x, dict) and 'assetPriceUSD' in x else 0
        )

        # Calculate amount in USD
        self.df['amountUSD'] = self.df['amount'] * self.df['assetPriceUSD']

        return True

    def engineer_features(self):
        """Engineers features for each user wallet."""
        if self.df is None:
            print("Data not loaded. Call load_and_preprocess_data first.")
            return

        # Group by userWallet to calculate features
        wallet_features = self.df.groupby('userWallet').agg(
            total_transactions=('txHash', 'nunique'),
            first_transaction_date=('timestamp', 'min'),
            last_transaction_date=('timestamp', 'max'),
            deposit_count=('action', lambda x: (x == 'deposit').sum()),
            borrow_count=('action', lambda x: (x == 'borrow').sum()),
            repay_count=('action', lambda x: (x == 'repay').sum()),
            redeem_count=('action', lambda x: (x == 'redeemunderlying').sum()),
            liquidation_count=('action', lambda x: (x == 'liquidationcall').sum())
        ).reset_index()

        # Calculate total USD amounts for different actions
        total_usd_by_action = self.df.groupby(['userWallet', 'action'])['amountUSD'].sum().unstack(fill_value=0)
        wallet_features = wallet_features.merge(
            total_usd_by_action.rename(columns={
                'deposit': 'total_deposit_usd',
                'borrow': 'total_borrow_usd',
                'repay': 'total_repay_usd',
                'redeemunderlying': 'total_redeem_usd',
                'liquidationcall': 'total_liquidation_usd'
            }),
            on='userWallet',
            how='left'
        ).fillna(0)

        # Activity duration
        wallet_features['activity_duration_days'] = (
            wallet_features['last_transaction_date'] - wallet_features['first_transaction_date']
        ).dt.days.fillna(0)
        # Ensure minimum duration of 1 day to avoid division by zero later
        wallet_features['activity_duration_days'] = wallet_features['activity_duration_days'].apply(lambda x: max(x, 1))


        # Average daily transactions
        wallet_features['avg_daily_transactions'] = wallet_features['total_transactions'] / wallet_features['activity_duration_days']

        # Net flow (simplified)
        wallet_features['net_flow_usd'] = wallet_features['total_deposit_usd'] - wallet_features['total_redeem_usd']

        # Borrow to repay ratio (handle division by zero)
        wallet_features['borrow_to_repay_ratio'] = wallet_features.apply(
            lambda row: row['total_borrow_usd'] / row['total_repay_usd'] if row['total_repay_usd'] > 0 else (
                1 if row['total_borrow_usd'] > 0 else 0
            ),
            axis=1
        )
        # Cap high ratios to prevent extreme values from dominating
        wallet_features['borrow_to_repay_ratio'] = wallet_features['borrow_to_repay_ratio'].replace([np.inf, -np.inf], np.nan).fillna(0)
        wallet_features['borrow_to_repay_ratio'] = np.minimum(wallet_features['borrow_to_repay_ratio'], 10) # Cap at 10 for extreme cases


        # Liquidation flag
        wallet_features['liquidation_flag'] = (wallet_features['liquidation_count'] > 0).astype(int)

        self.wallet_features = wallet_features # Assign the engineered features to the instance variable
        return wallet_features

    def calculate_scores(self):
        """Calculates a credit score for each wallet based on engineered features."""
        if self.wallet_features is None:
            print("Features not engineered. Call engineer_features first.")
            return

        features_df = self.wallet_features.copy() # Work on a copy

        # Define features and their desired impact (positive or negative on score)
        # Higher values of positive features increase score, higher values of negative features decrease score
        positive_features = [
            'total_deposit_usd',
            'repay_count',
            'net_flow_usd',
            'activity_duration_days',
            'avg_daily_transactions'
        ]
        negative_features = [
            'borrow_count',
            'borrow_to_repay_ratio',
            'liquidation_flag'
        ]

        # Apply transformations and scaling
        scaled_features = pd.DataFrame(index=features_df.index)

        # Scale positive features (Min-Max scaling to 0-1)
        for feature in positive_features:
            if features_df[feature].max() > 0:
                scaled_features[f'scaled_{feature}'] = (features_df[feature] - features_df[feature].min()) / (features_df[feature].max() - features_df[feature].min())
            else:
                scaled_features[f'scaled_{feature}'] = 0

        # Scale negative features (Min-Max scaling, then invert for scoring)
        for feature in negative_features:
            if features_df[feature].max() > 0:
                scaled_features[f'scaled_{feature}'] = 1 - ((features_df[feature] - features_df[feature].min()) / (features_df[feature].max() - features_df[feature].min()))
            else:
                scaled_features[f'scaled_{feature}'] = 1
            if feature == 'liquidation_flag':
                scaled_features[f'scaled_{feature}'] = 1 - features_df[feature]


        # Define weights for each scaled feature (these are illustrative and can be tuned)
        weights = {
            'scaled_total_deposit_usd': 0.25,
            'scaled_repay_count': 0.20,
            'scaled_net_flow_usd': 0.15,
            'scaled_activity_duration_days': 0.10,
            'scaled_avg_daily_transactions': 0.05,
            'scaled_borrow_count': 0.05,
            'scaled_borrow_to_repay_ratio': 0.10,
            'scaled_liquidation_flag': 0.10,
        }

        # Calculate the raw score based on weights
        for feature in weights.keys():
            if feature not in scaled_features.columns:
                scaled_features[feature] = 0

        raw_scores = sum(scaled_features[feature] * weights[feature] for feature in weights.keys())

        # Normalize the raw scores to a 0-1000 range
        min_raw_score = raw_scores.min()
        max_raw_score = raw_scores.max()

        if max_raw_score == min_raw_score:
            self.wallet_features['credit_score'] = 500 # Assign a neutral score
        else:
            self.wallet_features['credit_score'] = ((raw_scores - min_raw_score) / (max_raw_score - min_raw_score)) * 1000

        # Store scores in the instance variable
        self.wallet_scores = self.wallet_features[['userWallet', 'credit_score']].set_index('userWallet')['credit_score'].to_dict()

        return self.wallet_scores

    def get_wallet_scores(self):
        """Returns the calculated wallet scores."""
        return self.wallet_scores

    def run(self):
        """Runs the complete scoring pipeline."""
        if not self.load_and_preprocess_data():
            return {}
        self.engineer_features()
        return self.calculate_scores()

if __name__ == "__main__":
    scorer = WalletScorer()
    scores = scorer.run()

    if scores:
        print("\n--- Wallet Credit Scores (Sample) ---")
        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        for wallet, score in sorted_scores[:10]:
            print(f"Wallet: {wallet}, Score: {score:.2f}")

        print("\n--- Score Distribution ---")
        if scorer.wallet_features is not None and 'credit_score' in scorer.wallet_features.columns:
            scores_df = scorer.wallet_features[['userWallet', 'credit_score']].copy()
            bins = [0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
            labels = ['0-100', '101-200', '201-300', '301-400', '401-500', '501-600', '601-700', '701-800', '801-900', '901-1000']
            scores_df['score_range'] = pd.cut(scores_df['credit_score'], bins=bins, labels=labels, right=False)
            distribution = scores_df['score_range'].value_counts().sort_index()
            print(distribution)

            print("\n--- Feature Insights (Example for Analysis) ---")
            features = scorer.wallet_features # Now this 'features' DataFrame includes 'credit_score'
            if not features.empty:
                high_score_wallets = features.nlargest(5, 'credit_score')
                low_score_wallets = features.nsmallest(5, 'credit_score')
                print("\nTop 5 Wallets by Score:")
                print(high_score_wallets[['userWallet', 'credit_score', 'total_deposit_usd', 'repay_count', 'liquidation_flag', 'borrow_to_repay_ratio']])
                print("\nBottom 5 Wallets by Score:")
                print(low_score_wallets[['userWallet', 'credit_score', 'total_deposit_usd', 'repay_count', 'liquidation_flag', 'borrow_to_repay_ratio']])
        else:
            print("No scores or 'credit_score' column found for analysis.")
