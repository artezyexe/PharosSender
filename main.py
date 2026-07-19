import json
import time
import random
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
from colorama import init, Fore, Style

init(autoreset=True)
Account.enable_unaudited_hdwallet_features()
load_dotenv()

# ============================================================
# KONFIGURASI
# ============================================================
RPC_URL      = os.getenv("RPC_URL",      "https://rpc.pharos.xyz")
TO_ADDRESS   = os.getenv("TO_ADDRESS",   "")
DELAY_MIN    = int(os.getenv("DELAY_MIN",    "1"))
DELAY_MAX    = int(os.getenv("DELAY_MAX",    "3"))
WALLET_FILE  = os.getenv("WALLET_FILE",  "wallet.txt")
WALLET_FILE2 = os.getenv("WALLET_FILE2", "walletv2.txt")
MAX_WORKERS  = int(os.getenv("MAX_WORKERS",  "3"))
MAX_RETRY    = int(os.getenv("MAX_RETRY",    "3"))   # retry saat 429
RETRY_DELAY  = int(os.getenv("RETRY_DELAY",  "5"))   # detik antar retry

GAS_LIMIT  = 21000
GAS_BUFFER = 1.2
HD_PATH    = "m/44'/60'/0'/0/0"

# Thread lock
print_lock = threading.Lock()
nonce_lock = threading.Lock()

# ============================================================
# WARNA
# ============================================================
W  = lambda t: f"{Style.BRIGHT}{Fore.WHITE}{t}{Style.RESET_ALL}"
G  = lambda t: f"{Fore.GREEN}{t}{Style.RESET_ALL}"
C  = lambda t: f"{Fore.CYAN}{t}{Style.RESET_ALL}"
Y  = lambda t: f"{Fore.YELLOW}{t}{Style.RESET_ALL}"
R  = lambda t: f"{Fore.RED}{t}{Style.RESET_ALL}"
M  = lambda t: f"{Fore.MAGENTA}{t}{Style.RESET_ALL}"
D  = lambda t: f"{Style.DIM}{t}{Style.RESET_ALL}"

def sp(*args, **kwargs):
    """Thread-safe print."""
    with print_lock:
        print(*args, **kwargs)

def divider(char="─", n=72, color=Fore.CYAN):
    with print_lock:
        print(f"{color}{char * n}{Style.RESET_ALL}")

def banner():
    divider("═")
    print(f"  {C('◈')}  {W('PHAROS MAINNET SENDER')}  {D('· Send ALL Balance · Multi-Account')}")
    divider("═")
    print(f"  {D('RPC      :')} {C(RPC_URL)}")
    print(f"  {D('Tujuan   :')} {C(TO_ADDRESS)}")
    print(f"  {D('Threads  :')} {G(str(MAX_WORKERS))} {D('paralel')}")
    print(f"  {D('Retry    :')} {W(str(MAX_RETRY))}x {D(f'(jeda {RETRY_DELAY}s)')}")
    print(f"  {D('Delay    :')} {W(f'{DELAY_MIN}–{DELAY_MAX}s')} {D('antar thread')}")
    divider("─")
    print()

def sect(title):
    with print_lock:
        pad = 54 - len(title)
        print(f"{D('┌─')} {Y(title.upper())} {D('─' * pad)}")

# ============================================================
# SEED PHRASE
# ============================================================
def is_seed_phrase(value):
    return len(value.strip().split()) in (12, 15, 18, 21, 24)

def seed_to_private_key(mnemonic):
    acct = Account.from_mnemonic(mnemonic, account_path=HD_PATH)
    return acct.key.hex()

# ============================================================
# LOAD WALLET
# ============================================================
def load_wallets(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(filepath)
    wallets, skipped = [], []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        for i, raw_line in enumerate(f, 1):
            raw = raw_line.strip()
            if not raw or raw.startswith("#"):
                continue
            if is_seed_phrase(raw):
                try:
                    pk = seed_to_private_key(raw)
                    pk = "0x" + pk if not pk.startswith("0x") else pk
                    wallets.append({"pk": pk, "src": "seed", "file": filepath, "line": i})
                    print(f"  {G('✓')} {D(filepath)} {C('[seed]')} {D(f'baris {i}')} → {G('derived OK')}")
                except Exception as e:
                    skipped.append((i, str(e)))
                continue
            pk = raw.replace(" ", "")
            if not pk.startswith("0x"):
                pk = "0x" + pk
            hex_part = pk[2:]
            if len(hex_part) != 64:
                skipped.append((i, f"panjang {len(hex_part)}/64"))
                continue
            try:
                int(hex_part, 16)
            except ValueError:
                skipped.append((i, "non-hex"))
                continue
            wallets.append({"pk": pk, "src": "privkey", "file": filepath, "line": i})
            print(f"  {G('✓')} {D(filepath)} {M('[privkey]')} {D(f'baris {i}')} → {G('valid')}")

    if skipped:
        for ln, reason in skipped:
            print(f"  {Y('⚠')} {D(f'baris {ln}:')} {R(reason)}")
    if wallets:
        print(f"  {D('loaded')} {W(str(len(wallets)))} {D('akun dari')} {C(filepath)}")
    return wallets

def load_wallets_multi(*filepaths):
    all_wallets = []
    for fp in filepaths:
        if not os.path.exists(fp):
            print(f"  {Y('⚠')} {D(f'tidak ditemukan: {fp}')}")
            continue
        all_wallets.extend(load_wallets(fp))
    if not all_wallets:
        raise ValueError("Tidak ada wallet valid.")
    print(f"{C('◈')} {D('total')} {W(str(len(all_wallets)))} {D('akun dimuat')}")
    return all_wallets

# ============================================================
# WEB3
# ============================================================
def connect_web3():
    w3 = Web3(Web3.HTTPProvider(
        RPC_URL,
        request_kwargs={"timeout": 30}
    ))
    if not w3.is_connected():
        raise ConnectionError(f"Gagal konek: {RPC_URL}")
    print(f"  {G('✓')} {D('chain connected')} · {D('chain id')} {W(str(w3.eth.chain_id))}")
    return w3

def get_balance(w3, address):
    return w3.eth.get_balance(Web3.to_checksum_address(address))

def to_pros(w3, wei):
    return float(w3.from_wei(wei, "ether"))

def rpc_call_with_retry(fn, *args, label="rpc call"):
    """Wrapper retry untuk semua RPC call — handle 429 otomatis."""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            return fn(*args)
        except Exception as e:
            err = str(e).lower()
            is_rate_limit = "429" in err or "too many" in err or "rate" in err
            if is_rate_limit and attempt < MAX_RETRY:
                wait = RETRY_DELAY * attempt  # backoff: 5s, 10s, 15s
                sp(f"  {Y('⚠')} {D(f'[{label}] 429 rate limit — retry {attempt}/{MAX_RETRY} dalam {wait}s...')}")
                time.sleep(wait)
                continue
            raise

# ============================================================
# PREVIEW SALDO (realtime per wallet)
# ============================================================
def preview_all_balances(w3, wallets):
    sect("saldo semua akun")

    W_NO  = 4
    W_ADD = 42
    W_SRC = 8
    W_BAL = 14

    hdr = (
        f"  {'No':>{W_NO}}  "
        f"{'Address':<{W_ADD}}  "
        f"{'Src':<{W_SRC}}  "
        f"{'Saldo (PROS)':>{W_BAL}}  "
        f"Status"
    )
    print()
    print(D(hdr))
    print(Fore.CYAN + "  " + "─" * 84 + Style.RESET_ALL)

    previews = []
    total    = 0

    for idx, w in enumerate(wallets, 1):
        no_s = str(idx).rjust(W_NO)
        try:
            addr  = Account.from_key(w["pk"]).address
            bal   = rpc_call_with_retry(get_balance, w3, addr, label=f"balance akun {idx}")
            total += bal
            pros  = to_pros(w3, bal)
            addr_s = addr[:W_ADD].ljust(W_ADD)
            bal_s  = f"{pros:.8f}".rjust(W_BAL)
            src_s  = w["src"].ljust(W_SRC)

            if bal > 0:
                print(f"  {D(no_s)}  {C(addr_s)}  {D(src_s)}  {G(bal_s)}  {G('✓ READY')}", flush=True)
            else:
                print(f"  {D(no_s)}  {C(addr_s)}  {D(src_s)}  {D(bal_s)}  {Y('⊘ SKIP ')}", flush=True)

            previews.append({"pk": w["pk"], "address": addr, "balance": bal})

        except Exception as e:
            print(f"  {D(no_s)}  {R('ERROR — ' + str(e)[:50])}", flush=True)
            previews.append({"pk": w["pk"], "address": "error", "balance": 0, "error": str(e)})

    print(Fore.CYAN + "  " + "─" * 84 + Style.RESET_ALL)
    total_pros = to_pros(w3, total)
    total_s    = f"{total_pros:.8f}".rjust(W_BAL)
    pad        = W_ADD + W_SRC + 4
    print(f"  {'':>{W_NO}}  {D('TOTAL SALDO GABUNGAN'):<{pad}}  {G(total_s)} {W('PROS')}")
    print(Fore.CYAN + "  " + "═" * 84 + Style.RESET_ALL)
    print()
    return previews

# ============================================================
# KIRIM SALDO — dengan retry 429
# ============================================================
def send_all_balance(w3, private_key, to_address):
    account   = Account.from_key(private_key)
    sender    = account.address

    balance   = rpc_call_with_retry(get_balance, w3, sender, label="balance")
    gas_price = int(rpc_call_with_retry(lambda: w3.eth.gas_price, label="gas_price") * GAS_BUFFER)
    gas_cost  = GAS_LIMIT * gas_price
    send_amt  = balance - gas_cost

    if send_amt <= 0:
        raise ValueError(
            f"Saldo tidak cukup. "
            f"saldo={to_pros(w3,balance):.8f} "
            f"gas={to_pros(w3,gas_cost):.8f}"
        )

    with nonce_lock:
        nonce = rpc_call_with_retry(
            lambda: w3.eth.get_transaction_count(sender),
            label="nonce"
        )

    tx = {
        "nonce":    nonce,
        "to":       Web3.to_checksum_address(to_address),
        "value":    send_amt,
        "gas":      GAS_LIMIT,
        "gasPrice": gas_price,
        "chainId":  w3.eth.chain_id,
    }

    signed  = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = rpc_call_with_retry(
        lambda: w3.eth.send_raw_transaction(signed.raw_transaction),
        label="send_tx"
    )
    tx_hex  = tx_hash.hex()

    receipt = rpc_call_with_retry(
        lambda: w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120),
        label="receipt"
    )

    return {
        "tx_hash":   tx_hex,
        "status":    receipt.status,
        "sent_wei":  send_amt,
        "sent_pros": str(to_pros(w3, send_amt)),
        "gas_cost":  gas_cost,
        "block":     receipt.blockNumber,
        "gas_used":  receipt.gasUsed,
    }

# ============================================================
# PROSES SATU AKUN (dipanggil tiap thread)
# ============================================================
def process_one(w3, idx, total, item, to_address):
    address = item["address"]
    balance = item["balance"]
    tag     = f"[{idx}/{total}]"

    if "error" in item:
        sp(f"  {Y('⚠')} {D(tag)} {C(address[:20]+'...')} {Y('→ error, dilewati')}")
        return {"account": address, "skipped": True, "reason": item["error"]}

    if balance == 0:
        sp(f"  {Y('⊘')} {D(tag)} {C(address[:20]+'...')} {Y('→ saldo kosong, dilewati')}")
        return {"account": address, "skipped": True, "reason": "saldo kosong"}

    pros = to_pros(w3, balance)
    sp(f"  {C('▶')} {D(tag)} {C(address)} {D('·')} {W(f'{pros:.8f}')} PROS")

    try:
        result  = send_all_balance(w3, item["pk"], to_address)
        sent    = float(result["sent_pros"])
        blk     = result["block"]

        if result["status"] == 1:
            sp(f"  {G('✓')} {D(tag)} {C(address[:20]+'...')} "
               f"{D('→')} {G(f'{sent:.8f}')} PROS "
               f"{D('· block')} {W(str(blk))} "
               f"{D('· hash')} {D(result['tx_hash'][:18]+'...')}")
        else:
            sp(f"  {R('✗')} {D(tag)} {C(address[:20]+'...')} {R('→ TX gagal')} {D(f'block {blk}')}")

        return {"account": address, **result}

    except Exception as e:
        sp(f"  {R('✗')} {D(tag)} {C(address[:20]+'...')} {R(f'→ {str(e)[:60]}')}")
        return {"account": address, "error": str(e)}

# ============================================================
# PARALEL EXECUTOR — BATCH MODE
# ============================================================
def process_all_accounts(w3, previews, to_address):
    sect("eksekusi paralel")

    total      = len(previews)
    results    = [None] * total
    # Bagi jadi batch sesuai MAX_WORKERS
    batches    = [previews[i:i+MAX_WORKERS] for i in range(0, total, MAX_WORKERS)]
    total_batch = len(batches)

    sp(f"  {C('◈')} {D('total akun ')} {W(str(total))} "
       f"{D('·')} {W(str(total_batch))} {D('batch')} "
       f"{D('·')} {W(str(MAX_WORKERS))} {D('wallet/batch')}\n")

    done = 0
    for b_idx, batch in enumerate(batches, 1):
        sp(f"  {D('─'*50)}")
        sp(f"  {M('▶')} {D('batch')} {W(f'{b_idx}/{total_batch}')} "
           f"{D('·')} {W(str(len(batch)))} {D('wallet diproses bersamaan...')}")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {}
            for item in batch:
                # global index di hasil
                g_idx = previews.index(item)
                fut   = executor.submit(process_one, w3, g_idx+1, total, item, to_address)
                future_map[fut] = g_idx

            for future in as_completed(future_map):
                slot = future_map[future]
                try:
                    results[slot] = future.result()
                except Exception as e:
                    results[slot] = {"account": f"slot_{slot}", "error": str(e)}
                done += 1

        # Delay antar batch — kecuali batch terakhir
        if b_idx < total_batch:
            delay = random.randint(DELAY_MIN, DELAY_MAX)
            sp(f"  {D(f'⏱  batch {b_idx} selesai · jeda {delay}s sebelum batch berikutnya...')}")
            time.sleep(delay)
        else:
            sp(f"  {G('✓')} {D('semua batch selesai')}")

    return results

# ============================================================
# RINGKASAN
# ============================================================
def print_summary(results, w3):
    sect("ringkasan")
    success = [r for r in results if r and r.get("status") == 1]
    failed  = [r for r in results if r and r.get("status") == 0]
    skipped = [r for r in results if r and r.get("skipped")]
    errors  = [r for r in results if r and "error" in r and not r.get("skipped")]

    total_sent = sum(int(r.get("sent_wei", 0)) for r in success)

    divider("─", 40, Fore.CYAN)
    print(f"  {G('✓')}  {D('sukses  ')}  {W(str(len(success)))}")
    print(f"  {R('✗')}  {D('gagal   ')}  {W(str(len(failed)))}")
    print(f"  {Y('⊘')}  {D('dilewati')}  {W(str(len(skipped)))}")
    print(f"  {Y('!')}  {D('error   ')}  {W(str(len(errors)))}")
    print(f"  {C('◈')}  {D('total   ')}  {W(str(len(results)))}")

    if total_sent > 0:
        divider("─", 40, Fore.GREEN)
        print(f"  {G('TOTAL TERKIRIM')}  "
              f"{G(f'{to_pros(w3, total_sent):.8f}')} {W('PROS')}  "
              f"{D(f'· {len(success)} tx sukses')}")
        divider("─", 40, Fore.GREEN)

    with open("results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"{G('✓')} {D('hasil disimpan ke')} {C('results.json')}")
    divider("═")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    banner()

    if not TO_ADDRESS:
        print(R("  ✗  TO_ADDRESS belum diisi di .env!"))
        exit(1)

    try:
        sect("loading wallets")
        wallets  = load_wallets_multi(WALLET_FILE, WALLET_FILE2)
        w3       = connect_web3()

        previews = preview_all_balances(w3, wallets)

        print(f"  {Y('⚠')}  {Y('Akan kirim SEMUA saldo ke')} {C(TO_ADDRESS)}")
        prompt  = W("  Ketik 'YA' untuk melanjutkan: ")
        confirm = input(prompt).strip()
        if confirm != "YA":
            print(f"{R('✗ Dibatalkan.')}")
            exit(0)

        results = process_all_accounts(w3, previews, TO_ADDRESS)
        print_summary(results, w3)

    except KeyboardInterrupt:
        print(f"\n  {R('⛔ Dihentikan.')}")
    except Exception as e:
        print(f"{R(f'✗ Error fatal: {e}')}")