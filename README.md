# Pharos Mainnet Sender

A Python script that **sweeps the entire balance** from multiple wallets to a single destination address on the Pharos network, in parallel (multi-threaded) with automatic retry on rate limits (HTTP 429).

## ✨ Features

- Supports wallets as **private keys** or **seed phrases** (12/15/18/21/24 words)
- Can load wallets from two files at once (`wallet.txt` & `walletv2.txt`, both optional — the script still runs even if only one exists)
- Real-time balance preview for all accounts before execution
- Parallel batch execution using `ThreadPoolExecutor`
- Automatic retry with backoff when the RPC returns a rate-limit error
- Random delay between batches to avoid spamming the RPC
- Summary results + full log saved to `results.json`
- Colored terminal output (colorama)

## 📋 Requirements

- Python 3.9+
- Access to a Pharos network RPC (or any compatible EVM RPC)

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/artezyexe/PharosSender.git
   cd PharosSender
   ```

2. **(Optional) Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux/Mac
   venv\Scripts\activate         # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install web3 eth-account python-dotenv colorama
   ```

   Or create a `requirements.txt` with:
   ```
   web3
   eth-account
   python-dotenv
   colorama
   ```
   then run `pip install -r requirements.txt`

4. **Set up the `.env` configuration file**
   ```env
   RPC_URL=https://rpc.pharos.xyz
   TO_ADDRESS=0xYourDestinationAddress
   DELAY_MIN=1
   DELAY_MAX=3
   WALLET_FILE=wallet.txt
   WALLET_FILE2=walletv2.txt
   MAX_WORKERS=3
   MAX_RETRY=3
   RETRY_DELAY=5
   ```

5. **Prepare the wallet file(s)**

   - `wallet.txt` — required.
   - `walletv2.txt` — **optional**. If this file doesn't exist, the script still runs and only loads wallets from `wallet.txt` (a "not found" warning for `walletv2.txt` will appear, which is normal).

   One wallet per line, either a private key or a seed phrase:
   ```
   0xabc123...def456
   word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12
   # lines starting with # are ignored
   ```

6. **Run the script**
   ```bash
   python main.py
   ```

## 🔁 Workflow

1. **Banner & configuration** — the script prints a summary of the configuration (RPC, destination address, thread count, retry, delay).
2. **Load wallets** — reads `wallet.txt` and `walletv2.txt`, validates each line (64-character hex private key or seed phrase), and derives the corresponding address.
3. **Web3 connection** — connects to the RPC and verifies the connection + chain ID.
4. **Balance preview** — fetches each account's balance in real time and displays a table (address, source, balance, ready/empty status), including the combined total balance.
5. **Manual confirmation** — the user must type `YES` to proceed with sending (a safety check).
6. **Parallel batch execution**:
   - All accounts are split into batches based on `MAX_WORKERS`.
   - Each batch is processed concurrently via `ThreadPoolExecutor`.
   - For each account: calculate gas price & gas cost, send the entire balance (`balance - gas cost`) to `TO_ADDRESS`, then wait for the transaction receipt.
   - If the RPC returns a rate-limit error (429), it automatically retries with an increasing delay.
   - There's a random delay (`DELAY_MIN`–`DELAY_MAX` seconds) between batches.
7. **Final summary** — shows the number of successful/failed/skipped/error transactions along with the total amount sent, and saves the full details to `results.json`.

## ⚠️ Security Warning

- **Never** commit the `.env`, `wallet.txt`, or `walletv2.txt` files to the repository — these files contain private keys/seed phrases that can be used to take over your funds.
- Add these to `.gitignore`:
  ```
  .env
  wallet.txt
  walletv2.txt
  results.json
  venv/
  ```
- Only use this script with wallets you own. Double-check that `TO_ADDRESS` is correct before confirming, since blockchain transactions are final and cannot be reversed.

## 💰 Donate

If this project is useful to you, your support is greatly appreciated:

| Chain | Address |
|---|---|
| EVM (ETH/BNB/Polygon/etc.) | `0x332ad1f9f1323acf0b10540ad485ad4ff87238b2` |
| Solana | `J991ULgATYPheujXjc9bomraZ6Gn5AZSYedAkqu3gTuL` |
| Tron | `TDYEhNUeBBnp5CdgJbNhgBS5tac6YRNC3P` |

## 📄 License

This project is licensed under [MIT](LICENSE).
