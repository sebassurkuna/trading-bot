package com.trading.tickproducer;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Punto de entrada del Tick Producer.
 *
 * <p>Job Spring Boot que cada hora consulta candles OHLCV
 * del Python Gateway (mt5-bridge-api) y publica
 * {@code TickMessageV1} en el topic {@code topic_ticks} de Kafka.</p>
 */
@SpringBootApplication
@EnableScheduling
public class TickProducerApplication {

    public static void main(String[] args) {
        SpringApplication.run(TickProducerApplication.class, args);
    }
}
