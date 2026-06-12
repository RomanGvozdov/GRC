import { AppShell, Badge, Button, Group, NavLink, Text, Title } from "@mantine/core";
import { Link, Outlet, useLocation } from "react-router-dom";
import { hasPermission, useAuth } from "../auth";
import { ROLE_LABELS } from "../labels";

const NAV_ITEMS = [
  { to: "/", label: "Дашборд", module: null },
  { to: "/risks", label: "Ризики", module: "risks" },
  { to: "/controls", label: "Контролі", module: "controls" },
  { to: "/gap-analysis", label: "Gap-аналіз", module: "frameworks" },
  { to: "/audits", label: "Аудити", module: "audits" },
  { to: "/policies", label: "Політики", module: "policies" },
  { to: "/reports", label: "Звіти", module: "reports" },
  { to: "/audit-log", label: "Журнал дій", module: "audit_log" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const items = NAV_ITEMS.filter(
    (item) => !item.module || hasPermission(user, item.module, "read"),
  ).map(({ to, label }) => ({ to, label }));
  if (hasPermission(user, "admin", "manage")) {
    items.push({ to: "/frameworks", label: "Каталоги" });
    items.push({ to: "/users", label: "Користувачі" });
    items.push({ to: "/roles", label: "Ролі" });
    items.push({ to: "/api-tokens", label: "API-токени" });
  }

  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 220, breakpoint: "sm" }} padding="md">
      <AppShell.Header p="sm">
        <Group justify="space-between">
          <Title order={3}>GRC</Title>
          <Group gap="xs">
            <Text size="sm">{user?.full_name}</Text>
            <Badge variant="light">{user ? ROLE_LABELS[user.role] : ""}</Badge>
            <Button variant="subtle" size="xs" onClick={logout}>
              Вийти
            </Button>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs">
        {items.map((item) => (
          <NavLink
            key={item.to}
            component={Link}
            to={item.to}
            label={item.label}
            active={
              item.to === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.to)
            }
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
