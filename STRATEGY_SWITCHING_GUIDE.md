# Strategy Switching Guide

## Current Configuration

**Default Strategy**: `sma_rsi_combo` (optimized for bear markets)
- **Win Rate**: 82.7% in bear markets
- **Signal Frequency**: 6.1%
- **Risk Profile**: Conservative, proven performance

## Manual Switching Options

### Option 1: Enable Adaptive Mode (Recommended for Bull Markets)

When bull market conditions occur, edit `config.json`:

```json
"adaptive_strategy": {
  "enabled": false,
  "bear_strategy": "sma_rsi_combo",
  "bull_strategy": "sma_rsi_impulse",
  "transition_strategy": "sma_rsi_impulse",
  "note": "Set enabled=true for adaptive mode in bull markets"
}
```

**Note**: Change `"enabled": false` to `"enabled": true` to activate adaptive mode.

**Benefits**:
- Automatically switches between strategies based on market conditions
- Uses `sma_rsi_impulse` in bull markets (46.2% win rate)
- Uses `sma_rsi_combo` in bear markets (82.7% win rate)
- Uses `sma_rsi_impulse` in transitions (81.8% win rate)

### Option 2: Manual Strategy Selection

For more control, you can modify the strategy functions directly in `strategy.py`:

#### Current Default (sma_rsi_combo):
```python
def short_entry_signal(sig: pd.Series, prev_sig: pd.Series, adaptive: bool = False, market_type: str = "bear") -> bool:
    return sma_rsi_combo_signal(sig, prev_sig)
```

#### Switch to sma_rsi_impulse:
```python
def short_entry_signal(sig: pd.Series, prev_sig: pd.Series, adaptive: bool = False, market_type: str = "bear") -> bool:
    return sma_rsi_impulse_signal(sig, prev_sig)
```

## Market Condition Indicators

### Bull Market Signals:
- Sustained price increases >5% over 5 days
- Risk-on regime (risk_on = true)
- Positive momentum indicators

### Bear Market Signals:
- Sustained price decreases >5% over 5 days  
- Risk-off regime (risk_on = false)
- Negative momentum indicators

### Transition Signals:
- Mixed regime signals
- Recent trend reversals
- High volatility periods

## Quick Switch Commands

### Enable Adaptive Mode:
```bash
# Edit config.json
sed -i 's/"enabled": false/"enabled": true/' config.json
```

### Disable Adaptive Mode:
```bash
# Edit config.json  
sed -i 's/"enabled": true/"enabled": false/' config.json
```

## Performance Summary

| Strategy | Bear Markets | Bull Markets | Transitions | Overall |
|----------|-------------|--------------|-------------|---------|
| sma_rsi_combo | 82.7% | 39.4% | 61.9% | 70.5% |
| sma_rsi_impulse | 77.4% | 46.2% | 81.8% | 73.2% |
| Adaptive | Auto-switches based on market conditions |

## Recommendation

**Current Market**: Bear market conditions
**Recommended**: `sma_rsi_combo` (default)
**When to Switch**: Enable adaptive mode when sustained bull market conditions are observed

## Implementation Notes

- The system maintains backward compatibility
- All existing functionality remains unchanged
- Strategy switching is configuration-driven
- No code changes required for basic switching
- Advanced users can modify strategy functions directly

## Monitoring

Monitor these metrics after switching:
- Win rate changes
- Signal frequency adjustments  
- Drawdown patterns
- Overall performance metrics

Use the equity logs and trade logs to track performance differences between strategies.
