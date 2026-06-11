import { AppShell, Badge, Button, Group, NavLink, Text, Title } from "@mantine/core";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import { ROLE_LABELS } from "../labels";

const NAV_ITEMS = [
  { to: "/", label: "Дашборд" },
  { to: "/risks", label: "Ризики" },
  { to: "/controls", label: "Контролі" },
  { to: "/gap-analysis", label: "Gap-аналіз" },
  { to: "/audit-log", label: "Журнал дій" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const items = [...NAV_ITEMS];
  if (user?.role === "admin") items.push({ to: "/users", label: "Користувачі" });

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
