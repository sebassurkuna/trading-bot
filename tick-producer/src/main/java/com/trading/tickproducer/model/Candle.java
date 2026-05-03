package com.trading.tickproducer.model;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * Representa una vela OHLCV individual devuelta por el Gateway.
 *
 * <p>Mapea el JSON de cada elemento del array {@code candles[]}
 * del endpoint {@code GET /api/v1/tick/{symbol}}.</p>
 */
public record Candle(

        Instant time,

        BigDecimal open,

        BigDecimal high,

        BigDecimal low,

        BigDecimal close,

        @JsonProperty("tick_volume")
        long tickVolume,

        int spread
) {
}
