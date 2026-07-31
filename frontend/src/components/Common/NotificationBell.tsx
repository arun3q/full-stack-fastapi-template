import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Bell, CheckCheck } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { featureApi, type NotificationPublic } from "@/lib/featureApi"

export function NotificationBell() {
  const queryClient = useQueryClient()

  const notificationsQuery = useQuery({
    queryKey: ["notifications"],
    queryFn: featureApi.notifications,
    refetchInterval: 60_000,
  })

  const unreadQuery = useQuery({
    queryKey: ["notifications-unread"],
    queryFn: featureApi.notificationUnreadCount,
    refetchInterval: 60_000,
  })

  const unread = unreadQuery.data?.count ?? 0
  const notifications = notificationsQuery.data?.data ?? []

  const markRead = useMutation({
    mutationFn: (id: string) => featureApi.markNotificationRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] })
    },
  })

  const markAll = useMutation({
    mutationFn: () => featureApi.markAllNotificationsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] })
    },
  })

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Notifications">
          <Bell className="size-4" />
          {unread > 0 ? (
            <span className="absolute flex size-4 items-center justify-center rounded-full bg-primary text-[10px] text-primary-foreground">
              {unread > 9 ? "9+" : unread}
            </span>
          ) : null}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel className="flex items-center justify-between">
          <span>Notifications</span>
          {unread > 0 ? (
            <button
              type="button"
              onClick={() => markAll.mutate()}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <CheckCheck className="size-3" /> Mark all read
            </button>
          ) : null}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {notifications.length === 0 ? (
          <p className="px-3 py-4 text-center text-sm text-muted-foreground">
            You're all caught up
          </p>
        ) : (
          <div className="max-h-80 overflow-y-auto">
            {notifications.map((notification: NotificationPublic) => (
              <button
                type="button"
                key={notification.id}
                onClick={() => {
                  if (!notification.read_at) markRead.mutate(notification.id)
                }}
                className={`flex w-full flex-col gap-0.5 px-3 py-2 text-left text-sm hover:bg-muted ${
                  notification.read_at ? "opacity-60" : ""
                }`}
              >
                <span className="font-medium">{notification.title}</span>
                {notification.body ? (
                  <span className="text-xs text-muted-foreground">
                    {notification.body}
                  </span>
                ) : null}
              </button>
            ))}
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
