from __future__ import annotations

from math import log1p


def map_exception_to_heuristic(
    exception_type: str | None,
    message: str,
    *,
    lang: str = "pt-BR",
) -> tuple[str, str, str, str, float]:
    """Map exception to heuristic fix suggestion.

    Returns (title, summary, cause, fix, confidence) in the requested language.
    Currently supports ``pt-BR`` and ``en``; any other value falls back to ``en``.
    """

    normalized_lang = (lang or "").lower()
    is_ptbr = normalized_lang.startswith("pt")

    et = (exception_type or "").lower()
    msg = message.lower()

    if "valueerror" in et or "invalid literal" in msg:
        if is_ptbr:
            title = "Erro de conversão de valor"
            summary = "Valores inválidos estão sendo convertidos sem validação prévia."
            cause = "Dados de entrada chegam em formato inesperado (por exemplo, string em vez de número)."
            fix = "Valide e saneie a entrada antes de converter (try/except, checagem de tipos ou Pydantic)."
        else:
            title = "Value conversion error"
            summary = "Invalid values are being converted without prior validation."
            cause = "Input data arrives in an unexpected format (for example, string instead of number)."
            fix = "Validate and sanitize input before converting (try/except, type checks or Pydantic)."
        conf = 0.8
    elif "keyerror" in et or ("keyerror" in msg or "chave" in msg and "não encontrada" in msg):
        if is_ptbr:
            title = "Campo ausente em dicionário ou payload"
            summary = "O código acessa chaves que podem não existir em dicionários ou JSON."
            cause = "Diferença entre o schema esperado e o payload real recebido."
            fix = "Use .get com valor padrão ou valide o schema com Pydantic/TypedDict antes de acessar."
        else:
            title = "Missing field in dict or payload"
            summary = "The code accesses keys that may not exist in dictionaries or JSON."
            cause = "Mismatch between expected schema and actual payload received."
            fix = "Use .get with a default value or validate the schema with Pydantic/TypedDict before access."
        conf = 0.8
    elif "connection" in et or "connectionerror" in msg or "conexão recusada" in msg:
        if is_ptbr:
            title = "Falha de conexão com serviço externo"
            summary = "Uma dependência (Redis, Postgres ou API externa) está indisponível ou instável."
            cause = "Rede instável, credenciais incorretas ou configuração de pool/timeout inadequada."
            fix = "Implemente retry com backoff, healthchecks e monitore conexões e pools."
        else:
            title = "Failed to connect to external service"
            summary = "A dependency (Redis, Postgres or external API) is unavailable or unstable."
            cause = "Unstable network, wrong credentials or misconfigured pool/timeout."
            fix = "Implement retry with backoff, health checks and monitor connections and pools."
        conf = 0.75
    elif "timeout" in et or "tempo esgotado" in msg:
        if is_ptbr:
            title = "Operação excedeu o tempo limite"
            summary = "Uma chamada a serviço externo está demorando mais do que o limite configurado."
            cause = "Consulta pesada, sobrecarga do serviço ou timeout muito baixo."
            fix = "Ajuste o timeout, otimize a consulta e, se necessário, use circuit breaker com fallback."
        else:
            title = "Operation exceeded timeout"
            summary = "A call to an external service is taking longer than the configured limit."
            cause = "Heavy query, overloaded service or timeout set too low."
            fix = "Adjust the timeout, optimize the query and, if needed, use a circuit breaker with fallback."
        conf = 0.75
    elif "integrityerror" in et or "unique constraint" in msg:
        if is_ptbr:
            title = "Violação de integridade (chave única)"
            summary = "Uma inserção ou atualização está violando uma restrição de unicidade no banco de dados."
            cause = "Falta de checagem prévia de existência ou condição de corrida entre múltiplas requisições."
            fix = "Adicione verificação de existência antes de inserir e/ou trate IntegrityError com retry idempotente."
        else:
            title = "Integrity violation (unique key)"
            summary = "An insert or update is violating a uniqueness constraint in the database."
            cause = "No prior existence check or race condition between multiple requests."
            fix = "Add an existence check before inserting and/or handle IntegrityError with idempotent retry."
        conf = 0.8
    elif "validationerror" in et or "pydantic" in msg:
        if is_ptbr:
            title = "Falha de validação de dados"
            summary = "Os dados recebidos não atendem ao contrato do modelo de validação."
            cause = "Payloads incompletos ou tipos incompatíveis em requests/eventos."
            fix = "Revise o modelo de validação e melhore mensagens de erro; valide próximo à borda da aplicação."
        else:
            title = "Data validation failure"
            summary = "Received data does not match the validation model contract."
            cause = "Incomplete payloads or incompatible types in requests/events."
            fix = "Review the validation model and improve error messages; validate close to the application boundary."
        conf = 0.8
    else:
        if is_ptbr:
            title = "Erro de aplicação"
            summary = "Foi detectado um erro recorrente na aplicação."
            cause = "Ainda não há causa exata, mas o cluster de erros indica um padrão específico."
            fix = "Investigue o stacktrace, adicione logs de contexto e escreva testes cobrindo o cenário."
        else:
            title = "Application error"
            summary = "A recurring error has been detected in the application."
            cause = "There is no exact root cause yet, but the error cluster indicates a specific pattern."
            fix = "Inspect the stack trace, add contextual logging and write tests covering this scenario."
        conf = 0.6

    return title, summary, cause, fix, conf


def confidence_from_occurrences(base_confidence: float, occurrences: int) -> float:
    """Adjust confidence based on number of occurrences."""

    boost = min(log1p(max(occurrences, 0)) / 5.0, 0.2)
    return min(base_confidence + boost, 1.0)

