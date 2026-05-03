package com.trading.tickproducer.model;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * Mensaje publicado en el topic {@code topic_ticks} de Kafka.
 *
 * <p>Contiene la información OHLCV de la última candle consultada
 * al Gateway, enriquecida con metadata de publicación.</p>
 *
 * <p>Kafka key: {@code symbol} para garantizar orden por símbolo
 * dentro de la misma partición.</p>
 *
 * @param symbol      símbolo forex (e.g. "EURUSDm")
 * @param open        precio de apertura
 * @param high        precio máximo
 * @param low         precio mínimo
 * @param close       precio de cierre
 * @param tickVolume  volumen de ticks en la barra
 * @param spread      spread al abrir la barra
 * @param time        hora de apertura de la candle (UTC)
 * @param period      período de la candle (e.g. "1h")
 * @param publishedAt instante en que se publicó el mensaje a Kafka
 */
public record TickMessageV1(

        String symbol,

        BigDecimal open,

        BigDecimal high,

        BigDecimal low,

        BigDecimal close,

        long tickVolume,

        int spread,

        Instant time,

        String period,

        Instant publishedAt
) {

    /**
     * Crea un {@code TickMessageV1} a partir de una {@link Candle} y su símbolo.
     *
     * @param symbol símbolo del instrumento
     * @param candle candle OHLCV del Gateway
     * @param period período solicitado
     * @return mensaje listo para publicar
     */
    public static TickMessageV1 fromCandle(String symbol, Candle candle, String period) {
        return new TickMessageV1(
                symbol,
                candle.open(),
                candle.high(),
                candle.low(),
                candle.close(),
                candle.tickVolume(),
                candle.spread(),
                candle.time(),
                period,
                Instant.now()
        );
    }
}
