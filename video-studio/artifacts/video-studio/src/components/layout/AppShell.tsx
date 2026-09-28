import { Link, useLocation } from "wouter"
import { useAuth } from "@workspace/replit-auth-web"
import { 
  LayoutDashboard, 
  Clapperboard, 
  Library, 
  FileText, 
  Mic, 
  ActivitySquare,
  Settings,
  LogOut,
  Video
} from "lucide-react"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: Clapperboard },
  { href: "/library", label: "Library", icon: Library },
  { href: "/scripts", label: "Scripts", icon: FileText },
  { href: "/voices", label: "Voices", icon: Mic },
  { href: "/jobs", label: "Jobs", icon: ActivitySquare },
  { href: "/settings", label: "Settings", icon: Settings },
]

export function AppShell({ children }: { children: React.ReactNode }) {
  const [location] = useLocation()
  const { user, logout } = useAuth()

  return (
    <div className="flex h-[100dvh] w-full bg-background overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-sidebar text-sidebar-foreground border-r border-sidebar-border flex flex-col shrink-0 transition-all">
        <div className="h-16 flex items-center px-6 border-b border-sidebar-border gap-3 font-semibold text-lg tracking-tight shrink-0">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-primary-foreground shadow-sm">
            <Video className="w-5 h-5" />
          </div>
          Video Studio
        </div>
        
        <nav className="flex-1 overflow-y-auto p-4 space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = location === item.href || (item.href !== "/" && location.startsWith(item.href))
            const Icon = item.icon
            return (
              <Link 
                key={item.href} 
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors group",
                  isActive 
                    ? "bg-sidebar-accent text-sidebar-accent-foreground" 
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                )}
              >
                <Icon className={cn("w-5 h-5", isActive ? "text-primary" : "text-sidebar-foreground/50 group-hover:text-sidebar-foreground/80")} />
                {item.label}
              </Link>
            )
          })}
        </nav>
        
        <div className="p-4 border-t border-sidebar-border shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex flex-col overflow-hidden">
              <span className="text-sm font-medium truncate">{user?.firstName || user?.email || "Creator"}</span>
              <span className="text-xs text-sidebar-foreground/50 truncate">Workspace</span>
            </div>
            <button 
              onClick={() => logout()}
              className="p-2 rounded-md text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
              title="Log out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        <div className="absolute inset-0 overflow-y-auto">
          <div className="mx-auto w-full max-w-6xl p-6 lg:p-10">
            {children}
          </div>
        </div>
      </main>
    </div>
  )
}
