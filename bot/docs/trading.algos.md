## Algo 1.. Low valatility .01 spread...
Using this streaming data and indicators, this algo has these steps:
- if the stock is not volital(tdb):
    - **Smart Direction Engine**: The algo dynamically selects Long or Short based on real-time Level 2 metrics:
        - **Go LONG** (Buy the Bid): If level_2_obi > 0.15 (strong bid support) AND liq_consump_rate > 0 (asks are getting aggressively eaten).
        - **Go SHORT** (Sell the Ask): If level_2_obi < -0.15 (heavy ask resistance) AND liq_consump_rate < 0 (bids are getting dropped).
    - algo places a opening order at the current bid/ask price at 20 shares.
    - in the opering order is a trigger order that will place a closing order sell/buy_to_cover at the current bid/ask
    - best case is the both order fill and you make .20 cents.
    - there is a timer for the opening order for 20 seconds.. if it does not fill it is canceled.
    - if the order fills, but the triggering closing order does not fill there is a 10 second timer and the order is canceled. then a market order is placed to just exit the position before thing change to fast and the position is a lost..

* Notes:
 - The hardcoded long/short flag has been replaced by the "Smart Direction" Level 2 Upgrade, increasing the win-rate by ensuring the algo trades *with* the immediate momentum.
 - IF the fill rate is 86% + this algo works good, and there has be a few optimal days that it would hit this..

 - OPTIONS NOT IMPLEMENTED YET... This will be implemented in the other servers that manages this algo......
    * Option B: Define the "TBD Volatility" Filter (The Safety Valve)
        We can protect the hard $0.01 scalp by aggressively guarding the book stability. If the order book is "hollow" on either side, slippage will wreck a naive $0.01 target.

        Condition: We only open positions when the Level 1 Gap is strictly < 0.02 AND abs(spread_volatility) < 0.03.
        Reasoning: This ensures that we are trading in a packed, highly liquid moment. As soon as spread_volatility jumps, it means the book is hollowing out, and the bot pauses trading until liquidity tightens back up.

    * Option C: Shift to "Dynamic Timers" & Immediate Bailout
        Right now, the 20s and 10s wait timers are blind. A massive sweeping algo could dump 50,000 shares in 2 seconds, but your algo will sit there and hold the bag.

        Condition: When an order is pending, we continuously monitor liq_consump_rate and level_2_obi.
        Action: If you are Long, and liq_consump_rate violently spikes Negative (massive selling sweep detected), we DON'T wait the 10 seconds. We execute the immediate Market-Out dump to kill the losing trade before the price actually drops.