package com.trading.tickproducer.service;

import com.trading.tickproducer.model.CandleResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;

/**
 * Cliente reactivo para el Python Gateway (mt5-bridge-api).
 *
 * <p>Consulta el endpoint {@code GET /api/v1/tick/{symbol}} para obtener
 * la candle de la hora anterior al instante de ejecución.</p>
 */
@Slf4j
@Service
public class CandleGatewayClient {

    private static final String CANDLE_ENDPOINT = "/api/v1/tick/{symbol}";
    private static final String PERIOD = "1h";
    private static final DateTimeFormatter ISO_FORMATTER =
            DateTimeFormatter.ISO_INSTANT;

    private final WebClient webClient;

    public CandleGatewayClient(WebClient gatewayWebClient) {
        this.webClient = gatewayWebClient;
    }

    /**
     * Consulta la candle de la hora anterior para el símbolo dado.
     *
     * <p>Tanto {@code from} como {@code to} apuntan al mismo instante:
     * el inicio de la hora anterior en GMT. Ejemplo: si son las 14:00:01 UTC,
     * ambos parámetros valdrán {@code 13:00:00Z}.</p>
     *
     * @param symbol símbolo forex (e.g. "EURUSDm")
     * @return candle response o {@code Mono.empty()} si hay error
     */
    public Mono<CandleResponse> fetchLastCandle(String symbol) {
        Instant now = Instant.now();
        Instant from = now.truncatedTo(ChronoUnit.HOURS).minus(1, ChronoUnit.HOURS);
        Instant to = from;

        String fromStr = ISO_FORMATTER.format(from.atOffset(ZoneOffset.UTC));
        String toStr = ISO_FORMATTER.format(to.atOffset(ZoneOffset.UTC));

        log.debug("Fetching candle for {} — time={} period={}",
                symbol, fromStr, PERIOD);

        return webClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path(CANDLE_ENDPOINT)
                        .queryParam("from", fromStr)
                        .queryParam("to", toStr)
                        .queryParam("period", PERIOD)
                        .build(symbol))
                .retrieve()
                .onStatus(
                        status -> status.is4xxClientError(),
                        response -> {
                            log.warn("Gateway returned {} for symbol {}",
                                    response.statusCode(), symbol);
                            return Mono.empty();
                        }
                )
                .onStatus(
                        status -> status.is5xxServerError(),
                        response -> {
                            log.error("Gateway server error {} for symbol {}",
                                    response.statusCode(), symbol);
                            return Mono.empty();
                        }
                )
                .bodyToMono(CandleResponse.class)
                .doOnNext(resp -> log.debug("Received {} candles for {}",
                        resp.count(), symbol))
                .onErrorResume(ex -> {
                    log.error("Failed to fetch candle for {}: {}",
                            symbol, ex.getMessage());
                    return Mono.empty();
                });
    }
}
