package com.trading.tickproducer;

import com.trading.tickproducer.config.TickProperties;
import com.trading.tickproducer.model.Candle;
import com.trading.tickproducer.model.CandleResponse;
import com.trading.tickproducer.model.TickMessageV1;
import com.trading.tickproducer.scheduler.TickScheduler;
import com.trading.tickproducer.service.CandleGatewayClient;
import com.trading.tickproducer.service.TickPublisherService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Mono;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

/**
 * Tests unitarios para {@link TickScheduler}.
 *
 * <p>Verifica que el scheduler consulta el Gateway para cada símbolo
 * configurado y publica los mensajes en Kafka correctamente.</p>
 */
@ExtendWith(MockitoExtension.class)
class TickSchedulerTest {

    @Mock
    private CandleGatewayClient gatewayClient;

    @Mock
    private TickPublisherService publisherService;

    @Captor
    private ArgumentCaptor<TickMessageV1> messageCaptor;

    private TickScheduler scheduler;
    private TickProperties properties;

    @BeforeEach
    void setUp() {
        properties = new TickProperties();
        properties.setSymbols(List.of("EURUSDm", "GBPUSDm"));
        properties.setTopic("topic_ticks");
        properties.setCron("0 0 * * * *");

        scheduler = new TickScheduler(gatewayClient, publisherService, properties);
    }

    @Test
    @DisplayName("Should fetch candles and publish tick messages for all symbols")
    void shouldFetchAndPublishForAllSymbols() throws InterruptedException {
        // Given
        Candle candle = new Candle(
                Instant.parse("2026-02-26T12:00:00Z"),
                new BigDecimal("1.08500"),
                new BigDecimal("1.08700"),
                new BigDecimal("1.08400"),
                new BigDecimal("1.08650"),
                5678L,
                2
        );
        CandleResponse response = new CandleResponse("EURUSDm", "1h", 1, List.of(candle));

        when(gatewayClient.fetchLastCandle(anyString())).thenReturn(Mono.just(response));
        when(publisherService.publish(any(TickMessageV1.class))).thenReturn(Mono.empty());

        // When
        scheduler.fetchAndPublishTicks();

        // Then — esperar un poco para que el Flux asíncrono termine
        Thread.sleep(500);

        verify(gatewayClient, times(2)).fetchLastCandle(anyString());
        verify(publisherService, times(2)).publish(messageCaptor.capture());

        List<TickMessageV1> published = messageCaptor.getAllValues();
        assertThat(published).hasSize(2);
        assertThat(published.getFirst().open()).isEqualByComparingTo("1.08500");
        assertThat(published.getFirst().close()).isEqualByComparingTo("1.08650");
    }

    @Test
    @DisplayName("Should skip symbols when gateway returns empty response")
    void shouldSkipWhenGatewayReturnsEmpty() throws InterruptedException {
        // Given
        CandleResponse emptyResponse = new CandleResponse("EURUSDm", "1h", 0, List.of());

        when(gatewayClient.fetchLastCandle("EURUSDm")).thenReturn(Mono.just(emptyResponse));
        when(gatewayClient.fetchLastCandle("GBPUSDm")).thenReturn(Mono.empty());

        // When
        scheduler.fetchAndPublishTicks();

        // Then
        Thread.sleep(500);

        verify(publisherService, never()).publish(any());
    }

    @Test
    @DisplayName("Should continue processing when one symbol fails")
    void shouldContinueOnIndividualFailure() throws InterruptedException {
        // Given
        Candle candle = new Candle(
                Instant.parse("2026-02-26T12:00:00Z"),
                new BigDecimal("1.30000"),
                new BigDecimal("1.30200"),
                new BigDecimal("1.29800"),
                new BigDecimal("1.30100"),
                3456L,
                3
        );
        CandleResponse successResponse = new CandleResponse("GBPUSDm", "1h", 1, List.of(candle));

        when(gatewayClient.fetchLastCandle("EURUSDm"))
                .thenReturn(Mono.error(new RuntimeException("Connection refused")));
        when(gatewayClient.fetchLastCandle("GBPUSDm"))
                .thenReturn(Mono.just(successResponse));
        when(publisherService.publish(any(TickMessageV1.class)))
                .thenReturn(Mono.empty());

        // When
        scheduler.fetchAndPublishTicks();

        // Then
        Thread.sleep(500);

        verify(publisherService, times(1)).publish(messageCaptor.capture());
        assertThat(messageCaptor.getValue().symbol()).isEqualTo("GBPUSDm");
    }
}
