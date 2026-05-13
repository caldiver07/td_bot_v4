## Streaming Service (This Service)
Receives the Streaming Level 1 and Level 2 data and calculates key metrics for different services to pull, via redis, and use for their specific algos.

All generic metrics (e.g. `spoofing_detected`, `smart_direction`, `pause_orders`, `time_to_clear`, `level_2_obi`) are purely calculated as data indicators. The logic that defines how these indicators combine to determine **what type** of trade should be taken is decoupled into `algo_type` tags. The Trading bots use this `algo_type` tag to execute correctly.

---

## Algo 1: `flat` (Flat Scalp) **BEING USED BY BOT
**Concept**: A super flat stock with ideally no volatility. We're literally skimming the bid and ask at a 1-cent gap. 
**Trigger Conditions**:
- `spoofing_detected == "no"`
- `smart_direction == "flat"`
- `pause_orders == False`
- `time_to_clear > 10.0` and `< 250.0`
- `spread_volatility <= 0` (Spread must be compressing, no ballooning spreads)
- `abs(vwap_distance_cents) <= 0.1` (Strictly within a tenth of a cent to center VWAP)
- `ba_gap <= 0.025` (Spread is narrow enough to safely scalp)
- `abs(self.level_2_obi) < 0.10`

**Execution**:
Opening:
- Places an opening limit order at the current bid/ask for a small lot (e.g. 20 shares).
- Uses an OTTO (One-Triggers-the-Other) trigger. The stock goes in, and immediately triggers an order to flip the bid/ask.
- Scalping exactly $0.01 off the spread.
- Hold for 60 seconds
- If price moves off target then exit before timer
Closing (EXIT):
- If canceled then try one more limit order and wait for 60 seconds
- if that does not fill then exit with Market order
Stock HOLDS (Stock Performance):
- there are two set of metrics used to evaluate performance
    - Opening Rolling 50 Orders placed/filled/canceled
    - Closing Rolling 50 Orders placed/filled/canceled
    - Opening Overall Order placed/filled/canceled
    - Closing Overall Order placed/filled/canceled
- if Opensing or closeing Rolling fill percent is below 74% after 20 trades the stock will be Paused for 30 minutes

**Note**: This algo isn't producing well enough historically but serves as the baseline low-volatility state.
---

## Algo 2: `s_rev` (Short Reversion Algo) **NOT USED.. NEED TO BACKTEST MORE...
**Concept**: Designed for catching highly stretched tops where momentum has died and liquidity is stalling. Based on reversion to the VWAP. Plays a "Maker" strategy for better spread capture.
**Trigger Conditions**:
- `vwap_distance_percent >= 0.5` (The stock is mathematically stretched +0.5% above its VWAP)
- `time_to_clear > 5.0` (Stalling out against dense liquidity limits)
- `liq_consump_rate < 10.0` (Liquidity is no longer being rapidly consumed)
- `level_2_obi < -0.15` (Sellers are heavily stacking the ask)

**Execution (WIP / Under Testing)**:
Opening:
- Acts as a Maker: Places Limit orders to Short at the Ask and covers at the Bid to avoid paying the volatile spread.
- Has tight bailouts (`level_2_obi > 0.20` or time > 45s) and targets the VWAP (`vwap_distance_cents <= 0.5`).
Closing (Exit):
- chart.vwap_distance_cents <= 0.5: (Winner)
- chart.level_2_obi > 0.20: (Bailout)
- current_time > entry_time + 120s: (Timeout)
---

## Algo 3: `momentum` (Momentum Breakout Algo)
**Concept**: Designed to ride strong directional momentum for larger, sustained price movements (tens to hundreds of dollars), rather than scalping pennies. This algorithm seeks out high-volatility, high-volume breakouts and breakdowns where the tape is moving aggressively.
**Trigger Conditions**:
- `smart_direction` is strongly `"long"` or `"short"` (Requires both Level 2 OBI and Level 1 tape consumption to vigorously agree).
- `abs(liq_consump_rate) > 50` (Aggressive sweeping of the Bid or Ask).
- `abs(level_2_obi) > 0.35` (Heavy structural support/resistance pushing the price).
- `time_to_clear < 5.0` (Fast, highly volatile tape eating through limit walls instantly).

**Execution (Proposed)**:
Opening:
- Takes directional trades (Market or aggressive Limit) in the direction of the momentum.
- Does not use 1-cent OTO limit targets. Uses trailing stops or percentage-based targets to let the winner run.
Closing (Exit):
- Bails out when momentum signals exhaustion (`abs(liq_consump_rate)` drops toward 0).
- Drops the position aggressively if `smart_direction` reverts to `"flat"` or hits the trailing stop.
---

## Algo 4: `shadow` (HFT Front-Running Algo)
**Concept**: Designed for Mega-cap, highly manipulated stocks (like NVDA, AAPL, MSFT). Instead of waiting for momentum to peak (which results in buying the HFT top), this algorithm "shadows" high-frequency trading algorithms by detecting their setup footprints. It looks for a massive Order Book Imbalance (OBI) flip (the "trap") paired with early, low-velocity liquidity consumption. This allows the bot to enter the trade milliseconds *before* the massive HFT tape sweep occurs.
**Trigger Conditions**:
- `abs(level_2_obi) > 0.30` (HFTs have pulled the fake spoofing walls and suddenly stacked the book heavily in the anticipated direction to form a trap).
- `abs(liq_consump_rate) > 5` and `abs(liq_consump_rate) < 25` (The tape sweep is just *starting*. We are front-running the > 50 explosion).
- `time_to_clear < 10.0` (The tape is volatile and preparing to chew through the remaining real liquidity).

**Execution (Proposed)**:
Opening:
- Takes market or aggressive limit orders the millisecond the localized tape ticks in the direction of the massive OBI wall, acting before the `liq_consump_rate` peaks.
Closing (Exit):
- **Exits into the HFT sweep.** Once the `liq_consump_rate` explodes (e.g., > 50) and then begins to decay, the institutional algorithms are taking profits. We sell to the retail crowd joining late, exiting the exact moment momentum peaks and begins dropping.
---

## Algo 5: `vwap` (VWAP Trend Algo)
**Concept**: A 2:1 risk-reward algorithmic structure utilizing the localized macro-VWAP. Instead of scalping arbitrary percentages or waiting for arbitrary trailing stops, this algorithm seeks confirmed continuous strength relative to VWAP and dynamically adjusts its exits based on VWAP variance.
**Trigger Conditions**:
- `vwap_trend` equals `"UP"` (for Longs) or `"DOWN"` (for Shorts).
- `vwap_distance_cents` validates the trend. (e.g. `vwap_distance_cents > 0` for a true UP trend entry, meaning price maintains baseline strength).
- Restricted execution: requires `can_short == true` for short triggers and `spoofing_detected == "no"`.

**Execution (Proposed)**:
Opening:
- **Transitional Entrance Check**: The algorithm explicitly looks for the *start* of the move rather than chasing an overextended trend. It requires one of the following:
  - **Trend Flip**: The `vwap_trend` just recently flipped into its current direction (e.g., from `"FLAT"` or `"DOWN"` into `"UP"` within the last few seconds).
  - **VWAP Crossover**: The price physically crossed the VWAP line, moving the `vwap_distance_cents` narrowly above or below 0 (e.g., trapped between 0.0 and 2.0 cents distance).
- **Directional Alignment**: When the VWAP flips to a direction, the corresponding `vwap_distance_cents` must match. If the trend flips `"UP"`, the distance must be positive. If it flips `"DOWN"`, the distance must be negative.
- Enters the trade only when this fresh transition and directional alignment are confirmed, ensuring we operate at the launch point.
Closing (Exit):
- Sets a 2:1 Take Profit. (Risk 10 to make 20).
- Dynamically bounds the target profit point using the average variance the stock historically strays from VWAP across a trading cycle. (e.g. If it regularly deviates 30 cents, exit halfway into the expansion).
- Enables "Early Exit" by monitoring the `vwap_distance_cents`. As distance climbs, the algorithm rides it, but instantly exits the position as soon as the `vwap_distance_cents` begins to slip/decay back toward VWAP, completely bypassing the wait for a full baseline reversion.

---

## ANALYSIS DATA
Use Elasticsearch Data
Indexes:
- streaming_v3
- bot_v3
- events_v3
---


## Metric Definitions:

### spoofing_detected:
**Definition**: A real-time flag ("yes" or "no") that identifies if large limits on the Level 2 order book are fake and being pulled/canceled rather than actually being traded against.
**How it Works**: 
The system watches the `net_consumption` (how fast limits are disappearing from the book). If a massive chunk of size vanishes (e.g., 50+ lots or 5,000+ shares disappear), it cross-references the actual *Time & Sales* (tape) for the last 10 trades. 
If the tape volume accounts for less than 15% of the "missing" shares, it deducts that the shares were not sold or bought into—they were just pulled/canceled by a market maker to trick the algorithms. It marks `spoofing_detected` as `"yes"`.
**Use Case**:
Spoofing creates a "mirage" of support or resistance. If an algorithm (like `flat` or `s_rev`) sees massive liquidity and tries to lean against it to secure a scalp, but that liquidity isn't real, the price will instantly collapse right through the bot's limit orders. If `spoofing_detected == "yes"`, the bot knows the Order Book Imbalance (OBI) is currently fake, and it should immediately abort or pause taking new trades until the "fake walls" are gone.

### level_2_obi (Level 2 Order Book Imbalance):
**Definition**: A weighted ratio that measures the balance of supply (Asks) versus demand (Bids) sitting in the top 5 levels of the Level 2 order book.
**How it Works**:
The metric analyzes the first 5 price levels on both the Bid and Ask sides of the Level 2 book. It applies a mathematical weight to prioritize liquidity closest to the current price (Level 1 gets a 1.0 weight, Level 2 gets 0.8, down to 0.2 for Level 5). 
The final value ranges from `-1.0` to `+1.0`:
- **Positive (+0.1 to +1.0)**: Bids (buyers) heavily outweigh Asks. There is significant support.
- **Negative (-0.1 to -1.0)**: Asks (sellers) heavily outweigh Bids. There is significant resistance.
- **Near Zero (~0.0)**: The book is perfectly balanced between buyers and sellers.
**Use Case**:
This metric is critical for determining trap doors in execution. 
- *For Algo 1 (Flat)*: If OBI is extremely high (e.g., +0.17) and you are acting as a Maker buying the bid, you will get stuck at the back of a massive buyer line. By the time your order fills, the momentum is dead, and your OTO exit on the Ask will timeout. Therefore, finding a perfectly balanced book (`abs(level_2_obi) < 0.10`) restricts entering into crowded queues, letting you rotate in and out of the $0.01 scalp instantly.
- *For Algo 2 (Short Reversion)*: Used to find heavy, insurmountable celling resistance (`level_2_obi < -0.15`), and is also used as an aggressive bailout trigger (`level_2_obi > 0.20`) if buyers suddenly show up out of nowhere.

### time_to_clear:
**Definition**: A calculated measurement of how many seconds it would take for market momentum to completely chew through all the limit orders currently resting in the Level 2 order book.
**How it Works**:
The metric establishes a real-time **Volume Per Second (VPS)** baseline by tracking the physical tape volume over the last ~30 seconds (60 ticks). It then calculates the sum of all resting Level 2 volume on both sides of the book. 
By dividing the total `level_2_volume` by the `VPS`, we get our `time_to_clear` in seconds.
**Use Case**:
This metric detects if a stock's volume matches its Level 2 limit walls, allowing bots to gauge how long they will likely have to wait for an order to fill. 
- **Time > 61.0 Seconds (Dead Stock)**: If the Level 2 book is massive but tape volume is dead, this metric skyrockets (e.g., > 100s). `Flat` Algo 1 explicitly avoids these (`> 61.0`) because its OTO (One-Triggers-the-Other) logic relies on a 60-second timeout lock. If a stock takes 100 seconds to clear limits, we mathematically know our exit limit order will timeout before the price reaches us.
- **Time < 5.0 Seconds (Volatile Stock)**: The stock is chewing through limits so fast that trying to place Maker limit orders is impossible because the price jumps instantly. We avoid this for `Flat` Algo 1 (`> 10.0`), but this environment is perfect for `s_rev` (`> 5.0`) when looking for exhausted volatility.

### liq_consump_rate (Liquidity Consumption Rate):
**Definition**: A momentum metric that measures exactly how fast the shares sitting exactly on the Bid or Ask (Level 1) are currently being eaten up or swept by market orders.
**How it Works**:
On every single incoming tick, the code isolates the innermost Bid and Ask limits. If the price has *not* changed since the last tick, but the amount of shares sitting there has decreased, the metric assumes those shares were "consumed" (traded against).
- `net_consumption = ask_consumed - bid_consumed`
- An Exponential Moving Average (EMA) is then applied: `(0.3 * net_consumption) + (0.7 * previous_rate)`.
This creates a rate that decays cleanly to zero when no shares are trading.
- **Positive (> 0)**: Asks are being consumed (Bullish tape pressure; buyers sweeping the ask).
- **Negative (< 0)**: Bids are being consumed (Bearish tape pressure; sellers hitting the bid).
- **Near Zero (~0)**: Low volume/Stalled (No one is crossing the spread).
**Use Case**:
This metric isolates active liquidity destruction without being fooled by massive fake walls sitting deep in Level 2.
- *For Algo 2 (Short Reversion)*: Used specifically to ensure top-tier momentum is *exhausted* before fading the move. It demands `liq_consump_rate < 10.0` (bullish momentum has stalled and asks are no longer being eaten) alongside a massive seller wall (`level_2_obi < -0.15`). 
- As an aggressive bailout trigger: If the algos are holding limits and suddenly `abs(rate) > 50`, it means a massive tape sweep is underway breaking through liquidity instantly, warning the bot to immediately reconsider its Maker limits.

### smart_direction:
**Definition**: A combined macro-trend indicator (`"long"`, `"short"`, `"flat"`) that establishes the true direction of the tape by requiring both Level 2 structure (OBI) and Level 1 momentum (Liquidity Consumption) to actively agree. 
**How it Works**:
Instead of flipping violently on every tick, it uses a **state machine with hysteresis**:
- **To break into a Trend**: Demands explosive consensus. To flip to `"long"`, the Level 2 book must be massively stacked with buyers (`OBI > 0.35`) **AND** tape momentum must be aggressively eating sellers (`liq_consump_rate > 50`). To flip `"short"`, it requires the exact inverse (`OBI < -0.35` and `rate < -50`).
- **To maintain the Trend**: Once a trend is established, it applies a relaxed threshold to stay in that trend so minor pullbacks don't trigger false flags. For a `"long"` to die and drop back to `"flat"`, support must genuinely break down (`OBI < 0.25`) and momentum must drop (`rate <= 0`). 
**Use Case**:
- *For Algo 1 (Flat)*: Flat Algo is strictly barred from trading unless `smart_direction == "flat"`. This successfully prevents the bot from attempting to Maker-Scalp a 1-cent gain when the stock is in a massive, mathematically proven breakout or breakdown.
- *For Directional Algos*: Creates a gold standard for "True Breakouts," meaning neither the fake Level 2 walls nor random tape sweeps can fool the bot. Both datasets must agree simultaneously to flip the flag.

### trend:
**Definition**: A strictly price-action based indicator that evaluates the localized physical movement of the Level 1 Bid over the last 30 ticks (about 15 seconds) to classify the stock as `"UP"`, `"DOWN"`, `"FLAT"`, or `"VOLATILE"`.
**How it Works**:
It isolates the last 30 valid bid prints and looks at two things:
1. **Directional Consistency**: What percentage of those ticks moved strictly UP versus purely DOWN? It requires `60%` consistency in one direction to qualify as a trend.
2. **Price Change Thresholds**: Even if the ticks consistently stepped up, it requires the total distance moved to exceed `0.02%` of the stock price. 
- **`"FLAT"`**: Triggers if there are zero shifts in the bid price over 30 ticks, *or* if the max variance between the highest and lowest price point during the trailing window was less than `0.02%` (i.e. perfectly tight consolidation).
- **`"VOLATILE"`**: Acts as the default catch-all. If the Bid-Ask spread arbitrarily gets blown out (wider than 1.5 cents AND wider than `0.25%` of the stock price), or if price consistency fails to meet the `60%` threshold, it throws the volatile flag.
**Use Case**:
Unlike `smart_direction` (which is an advanced derivative of Level 2 walls and hidden consumption), `trend` is purely physical tape movement. 
- It acts as a localized "common sense" check. If `trend == "VOLATILE"`, the stock's spread is breaking algorithm rules or chopping erratically without a clear 60% directional leaning. 
- It acts great in tandem with `smart_direction`. For example, `smart_direction` might think the stock is `"long"` because OBI is heavily skewed and consumption is high, but if `trend` is `"FLAT"`, it means those buyers are completely trapped at the same price and unable to actually move the Bid higher.

### avg_vwap_extension:
**Definition**: A rolling average measuring exactly how far (in cents) the stock physically extends away from the VWAP during active trend waves. 
**How it Works**:
The backend tracks the active `vwap_distance_cents` peak during every `"UP"` or `"DOWN"` trend. When the trend exhausts and flips back to `"FLAT"`, the highest distance reached during that wave is recorded in the `vwap_peaks_history` array (a trailing 10-wave list). `avg_vwap_extension` calculates the mean of those historical expansion peaks natively.
**Use Case**:
- *For Algo 5 (VWAP)*: Removes guesswork from taking profits. By packing `avg_vwap_extension` in the payload, the trading bots instantly inherit the dynamic math indicating exactly how far a VWAP-based wave typically runs on this specific stock. Allows precise bracketing for the 2:1 exit logic.


