package com.trading.tickproducer.scheduler;

import com.trading.tickproducer.config.TickProperties;
import com.trading.tickproducer.model.CandleResponse;
import com.trading.tickproducer.model.TickMessageV1;
import com.trading.tickproducer.service.CandleGatewayClient;
import com.trading.tickproducer.service.TickPublisherService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Job programado que cada hora consulta candles del Gateway
 * y publica {@link TickMessageV1} en Kafka.
 *
 * <p>Para cada símbolo configurado en {@link TickProperties#getSymbols()},
 * consulta la candle de la hora anterior y la publica en
 * {@code topic_ticks} con key = símbolo.</p>
 *
 * <p>El procesamiento se realiza de forma reactiva con {@link Flux},
 * permitiendo concurrencia controlada entre llamadas al Gateway.</p>
 */
@Slf4j
@Component
public class TickScheduler {

    private static final int CONCURRENCY = 3;
    private static final String PERIOD = "1h";

    private final CandleGatewayClient gatewayClient;
    private final TickPublisherService publisherService;
    private final TickProperties tickProperties;

    public TickScheduler(
            CandleGatewayClient gatewayClient,
            TickPublisherService publisherService,
            TickProperties tickProperties
    ) {
        this.gatewayClient = gatewayClient;
        this.publisherService = publisherService;
        this.tickProperties = tickProperties;
    }

    /**
     * Ejecuta el ciclo de ingesta de ticks.
     *
     * <p>Se dispara según la expresión cron configurada
     * (por defecto {@code 0 0 * * * *} — cada hora en punto).</p>
     */
    @Scheduled(cron = "${tick.cron}")
    public void fetchAndPublishTicks() {
        List<String> symbols = tickProperties.getSymbols();
        Instant startTime = Instant.now();

        log.info("══ Tick cycle started — {} symbols to process ══", symbols.size());

        AtomicInteger successCount = new AtomicInteger(0);
        AtomicInteger errorCount = new AtomicInteger(0);

        Flux.fromIterable(symbols)
                .flatMap(this::processSymbol, CONCURRENCY)
                .doOnNext(msg -> successCount.incrementAndGet())
                .doOnError(ex -> {
                    errorCount.incrementAndGet();
                    log.error("Unexpected error in tick cycle: {}", ex.getMessage());
                })
                .doOnComplete(() -> {
                    Duration elapsed = Duration.between(startTime, Instant.now());
                    log.info("══ Tick cycle completed — success={} errors={} elapsed={}ms ══",
                            successCount.get(), errorCount.get(), elapsed.toMillis());
                })
                .subscribe();
    }

    /**
     * Procesa un símbolo individual: consulta al Gateway y publica en Kafka.
     *
     * @param symbol símbolo forex a procesar
     * @return Mono que emite el mensaje publicado o vacío si hay error
     */
    private Flux<TickMessageV1> processSymbol(String symbol) {
        return gatewayClient.fetchLastCandle(symbol)
                .filter(response -> response.lastCandle() != null)
                .map(response -> TickMessageV1.fromCandle(
                        response.symbol(), response.lastCandle(), PERIOD))
                .flatMap(message -> publisherService.publish(message)
                        .thenReturn(message))
                .doOnNext(msg -> log.debug("Processed {} — candle time={}",
                        msg.symbol(), msg.time()))
                .flux()
                .onErrorResume(ex -> {
                    log.error("Failed to process symbol {}: {}", symbol, ex.getMessage());
                    return Flux.empty();
                });
    }
}
