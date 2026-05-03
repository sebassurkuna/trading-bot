package com.trading.tickproducer.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

import java.util.List;

/**
 * Propiedades de configuración del scheduler de ticks.
 *
 * <p>Se bindean desde {@code application.yml} bajo el prefijo {@code tick}.</p>
 *
 * <p>Ejemplo de configuración:</p>
 * <pre>{@code
 * tick:
 *   topic: topic_ticks
 *   cron: "0 0 * * * *"
 *   symbols: EURUSDm,GBPUSDm,USDJPYm
 * }</pre>
 */
@Getter
@Setter
@Configuration
@ConfigurationProperties(prefix = "tick")
public class TickProperties {

    /** Topic de Kafka donde se publican los {@code TickMessageV1}. */
    private String topic = "topic_ticks";

    /** Expresión cron para el scheduler (por defecto cada hora en punto). */
    private String cron = "0 0 * * * *";

    /** Lista de símbolos forex a consultar. */
    private List<String> symbols = List.of(
            "EURUSDm",
            "GBPUSDm",
            "USDJPYm",
            "AUDUSDm",
            "USDCHFm",
            "USDCADm"
    );
}
