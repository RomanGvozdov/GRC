import { Button, Card, Group, Select, SimpleGrid, Text, Title } from "@mantine/core";
import { useState } from "react";
import { api, type AuditBrief, type Framework } from "../api";
import { useFetch } from "../components/shared";
import { downloadBlob } from "../labels";

export default function ReportsPage() {
  const { data: frameworks } = useFetch<Framework[]>("/frameworks");
  const { data: audits } = useFetch<AuditBrief[]>("/audits");
  const [gapFramework, setGapFramework] = useState<string | null>(null);
  const [auditId, setAuditId] = useState<string | null>(null);
  const [soaFramework, setSoaFramework] = useState<string | null>("iso27001");
  const [busy, setBusy] = useState<string | null>(null);

  async function download(key: string, url: string, filename: string) {
    setBusy(key);
    try {
      const { data } = await api.get(url, { responseType: "blob" });
      downloadBlob(data, filename);
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <Title order={2} mb="md">
        Звіти (PDF)
      </Title>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Card withBorder padding="md">
          <Title order={4}>Реєстр ризиків</Title>
          <Text size="sm" c="dimmed" mb="md">
            Повний реєстр з оцінками, рівнями та стратегіями обробки
          </Text>
          <Button
            loading={busy === "risks"}
            onClick={() => void download("risks", "/reports/risk-register", "risk_register.pdf")}
          >
            Завантажити
          </Button>
        </Card>

        <Card withBorder padding="md">
          <Title order={4}>Стан комплаєнсу (gap-аналіз)</Title>
          <Text size="sm" c="dimmed" mb="md">
            Покриття вимог обраного фреймворка контролями
          </Text>
          <Group align="end">
            <Select
              label="Фреймворк"
              data={frameworks?.map((f) => ({ value: String(f.id), label: f.name })) ?? []}
              value={gapFramework}
              onChange={setGapFramework}
              w={280}
            />
            <Button
              disabled={!gapFramework}
              loading={busy === "gap"}
              onClick={() =>
                void download("gap", `/reports/gap-analysis/${gapFramework}`, "gap_analysis.pdf")
              }
            >
              Завантажити
            </Button>
          </Group>
        </Card>

        <Card withBorder padding="md">
          <Title order={4}>Звіт за результатами аудиту</Title>
          <Text size="sm" c="dimmed" mb="md">
            Чек-лист, знахідки та коригувальні дії
          </Text>
          <Group align="end">
            <Select
              label="Аудит"
              data={audits?.map((a) => ({ value: String(a.id), label: `${a.code} ${a.title}` })) ?? []}
              value={auditId}
              onChange={setAuditId}
              w={280}
            />
            <Button
              disabled={!auditId}
              loading={busy === "audit"}
              onClick={() => void download("audit", `/reports/audit/${auditId}`, "audit_report.pdf")}
            >
              Завантажити
            </Button>
          </Group>
        </Card>

        <Card withBorder padding="md">
          <Title order={4}>Положення про застосовність (SoA)</Title>
          <Text size="sm" c="dimmed" mb="md">
            Statement of Applicability за ISO 27001 з обґрунтуваннями виключень
          </Text>
          <Group align="end">
            <Select
              label="Фреймворк"
              data={frameworks?.map((f) => ({ value: f.code, label: f.name })) ?? []}
              value={soaFramework}
              onChange={setSoaFramework}
              w={280}
            />
            <Button
              disabled={!soaFramework}
              loading={busy === "soa"}
              onClick={() =>
                void download("soa", `/reports/soa?framework_code=${soaFramework}`, "soa.pdf")
              }
            >
              Завантажити
            </Button>
          </Group>
        </Card>
      </SimpleGrid>
    </>
  );
}
