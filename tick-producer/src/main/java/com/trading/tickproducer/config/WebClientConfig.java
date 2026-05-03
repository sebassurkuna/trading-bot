package com.trading.tickproducer.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;

/**
 * Configuración del {@link WebClient} reactivo para comunicación
 * con el Python Gateway (mt5-bridge-api).
 */
@Configuration
public class WebClientConfig {

    @Value("${gateway.base-url}")
    private String gatewayBaseUrl;

    /**
     * Bean de {@link WebClient} preconfigurado con la base URL del Gateway,
     * headers por defecto y timeouts razonables.
     *
     * @param builder builder inyectado por Spring
     * @return instancia configurada de WebClient
     */
    @Bean
    public WebClient gatewayWebClient(WebClient.Builder builder) {
        return builder
                .baseUrl(gatewayBaseUrl)
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .build();
    }
}
