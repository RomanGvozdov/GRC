import {
  Alert,
  Badge,
  Button,
  FileButton,
  Group,
  Modal,
  Stack,
  Table,
  Text,
} from "@mantine/core";
import { useState } from "react";
import { api, errorText, type ImportReport } from "../api";
import { downloadBlob } from "../labels";

interface Props {
  opened: boolean;
  onClose: () => void;
  kind: "risks" | "controls";
  onImported: () => void;
}

export default function ImportModal({ opened, onClose, kind, onImported }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const downloadTemplate = () => {
    api
      .get(`/imports/template/${kind}`, { responseType: "blob" })
      .then(({ data }) => downloadBlob(data, `import_${kind}_template.xlsx`));
  };

  async function upload(dryRun: boolean) {
    if (!file) return;
    setError("");
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post<ImportReport>(
        `/imports/${kind}?dry_run=${dryRun}`,
        form,
      );
      setReport(data);
      if (!dryRun && data.created > 0) {
        onImported();
      }
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  function close() {
    setFile(null);
    setReport(null);
    setError("");
    onClose();
  }

  return (
    <Modal
      opened={opened}
      onClose={close}
      title={kind === "risks" ? "Імпорт ризиків з Excel" : "Імпорт контролів з Excel"}
      size="lg"
    >
      <Stack>
        {error && (
          <Alert color="red" onClose={() => setError("")} withCloseButton>
            {error}
          </Alert>
        )}
        <Group>
          <Button variant="default" onClick={downloadTemplate}>
            Завантажити шаблон
          </Button>
          <FileButton onChange={(f) => { setFile(f); setReport(null); }} accept=".xlsx">
            {(props) => <Button {...props}>{file ? file.name : "Обрати файл…"}</Button>}
          </FileButton>
        </Group>
        <Text size="sm" c="dimmed">
          Невідомі категорії та системи (ІКС) буде створено автоматично. Відповідальний
          шукається за email, вимоги — за кодами через кому.
        </Text>

        {file && !report && (
          <Button onClick={() => void upload(true)} loading={busy}>
            Перевірити файл (без збереження)
          </Button>
        )}

        {report && (
          <>
            <Group>
              <Badge color="green" variant="light">
                Валідних рядків: {report.valid_rows}
              </Badge>
              <Badge color={report.errors.length ? "red" : "gray"} variant="light">
                З помилками: {report.errors.length}
              </Badge>
              {!report.dry_run && <Badge color="blue">Імпортовано: {report.created}</Badge>}
            </Group>
            {report.errors.length > 0 && (
              <Table>
                <Table.Tbody>
                  {report.errors.map((err) => (
                    <Table.Tr key={err.row}>
                      <Table.Td w={90}>Рядок {err.row}</Table.Td>
                      <Table.Td>{err.message}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
            {report.dry_run && report.valid_rows > 0 && (
              <Button onClick={() => void upload(false)} loading={busy}>
                Імпортувати {report.valid_rows} рядків
                {report.errors.length > 0 ? " (рядки з помилками буде пропущено)" : ""}
              </Button>
            )}
            {!report.dry_run && <Button onClick={close}>Готово</Button>}
          </>
        )}
      </Stack>
    </Modal>
  );
}
