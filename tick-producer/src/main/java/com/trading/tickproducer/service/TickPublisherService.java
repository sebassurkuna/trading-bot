package com.trading.tickproducer.service;

import com.trading.tickproducer.config.TickProperties;
import com.trading.tickproducer.model.TickMessageV1;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

import java.util.concurrent.CompletableFuture;

/**
 * Servicio encargado de publicar {@link TickMessageV1} en Kafka.
 *
 * <p>Publica en el topic configurado en {@link TickProperties#getTopic()}
 * usando el símbolo como key para garantizar orden por instrumento
 * dentro de la misma partición.</p>
 */
@Slf4j
@Service
public class TickPublisherService {

    private final KafkaTemplate<String, TickMessageV1> kafkaTemplate;
    private final TickProperties tickProperties;

    public TickPublisherService(
            KafkaTemplate<String, TickMessageV1> kafkaTemplate,
            TickProperties tickProperties
    ) {
        this.kafkaTemplate = kafkaTemplate;
        this.tickProperties = tickProperties;
    }

    /**
     * Publica un {@link TickMessageV1} en el topic de Kafka.
     *
     * @param message mensaje a publicar
     * @return {@code Mono<Void>} que completa cuando Kafka confirma la escritura
     */
    public Mono<Void> publish(TickMessageV1 message) {
        String topic = tickProperties.getTopic();
        String key = message.symbol();

        log.debug("Publishing TickMessageV1 to topic={} key={} time={}",
                topic, key, message.time());

        CompletableFuture<SendResult<String, TickMessageV1>> future =
                kafkaTemplate.send(topic, key, message);

        return Mono.fromFuture(future)
                .doOnSuccess(result -> {
                    var metadata = result.getRecordMetadata();
                    log.info("Published {} → topic={} partition={} offset={}",
                            key, metadata.topic(), metadata.partition(), metadata.offset());
                })
                .doOnError(ex -> log.error("Failed to publish {} to {}: {}",
                        key, topic, ex.getMessage()))
                .then();
    }
}
