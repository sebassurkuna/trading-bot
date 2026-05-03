package com.trading.tickproducer.model;

import java.util.List;

/**
 * DTO que mapea la respuesta completa del Gateway de candles.
 *
 * <p>Corresponde al JSON devuelto por
 * {@code GET /api/v1/tick/{symbol}?from=...&to=...&period=1h}.</p>
 *
 * <p>Ejemplo:</p>
 * <pre>{@code
 * {
 *   "symbol": "EURUSDm",
 *   "period": "1h",
 *   "count": 1,
 *   "candles": [ { ... } ]
 * }
 * }</pre>
 */
public record CandleResponse(

        String symbol,

        String period,

        int count,

        List<Candle> candles
) {

    /**
     * Devuelve la última candle del array (la más reciente).
     *
     * @return última candle o {@code null} si el array está vacío
     */
    public Candle lastCandle() {
        if (candles == null || candles.isEmpty()) {
            return null;
        }
        return candles.getLast();
    }
}
