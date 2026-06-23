import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText, type AiAnswer } from "../api";
import { useAuth } from "../auth";

const SOURCE_PATHS: Record<string, string> = {
  requirement: "/frameworks",
  control: "/controls",
  policy: "/policies",
};

const SOURCE_LABELS: Record<string, string> = {
  requirement: "Вимога",
  control: "Контроль",
  policy: "Політика",
};

export default function AiSearchPage() {
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<AiAnswer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [indexMsg, setIndexMsg] = useState("");

  async function ask() {
    if (query.trim().length < 3) return;
    setError("");
    setBusy(true);
    setAnswer(null);
    try {
      const { data } = await api.post<AiAnswer>("/ai/ask", { query });
      setAnswer(data);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function reindex() {
    setError("");
    setIndexMsg("");
    setBusy(true);
    try {
      const { data } = await api.post<{ indexed: number }>("/ai/index");
      setIndexMsg(`Проіндексовано джерел: ${data.indexed}`);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>AI-пошук по базі знань</Title>
        {user?.role === "admin" && (
          <Button variant="default" onClick={() => void reindex()} loading={busy}>
            Переіндексувати
          </Button>
        )}
      </Group>

      <Text size="sm" c="dimmed" mb="md">
        Семантичний пошук і відповіді на основі каталогів, контролів і політик.
        Відповідь формується лише з наявних джерел і містить посилання на них.
        AI нічого не змінює в системі.
      </Text>

      {error && (
        <Alert color="red" mb="md" onClose={() => setError("")} withCloseButton>
          {error}
        </Alert>
      )}
      {indexMsg && (
        <Alert color="green" mb="md" onClose={() => setIndexMsg("")} withCloseButton>
          {indexMsg}
        </Alert>
      )}

      <Textarea
        placeholder="Напр.: які вимоги стосуються резервного копіювання?"
        value={query}
        onChange={(e) => setQuery(e.currentTarget.value)}
        autosize
        minRows={2}
        mb="sm"
      />
      <Button onClick={() => void ask()} loading={busy} disabled={query.trim().length < 3}>
        Запитати
      </Button>

      {answer && (
        <Card withBorder padding="md" mt="md">
          <Text style={{ whiteSpace: "pre-wrap" }}>{answer.answer}</Text>
          {answer.citations.length > 0 && (
            <>
              <Text size="sm" fw={600} mt="md" mb="xs">
                Джерела
              </Text>
              <Group gap="xs">
                {answer.citations.map((c, i) => (
                  <Anchor
                    key={i}
                    component={Link}
                    to={SOURCE_PATHS[c.source_type] ?? "/"}
                    size="sm"
                  >
                    <Badge variant="light">
                      {SOURCE_LABELS[c.source_type] ?? c.source_type} #{c.source_id} ·{" "}
                      {Math.round(c.score * 100)}%
                    </Badge>
                  </Anchor>
                ))}
              </Group>
            </>
          )}
        </Card>
      )}
    </>
  );
}
