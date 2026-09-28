import { Loader2 } from "lucide-react"

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={`animate-spin ${className || 'h-4 w-4'}`} />
}

export function PageLoading() {
  return (
    <div className="min-h-[50vh] flex flex-col items-center justify-center text-muted-foreground gap-4">
      <Spinner className="h-8 w-8 text-primary" />
      <p className="text-sm font-medium">Loading...</p>
    </div>
  )
}

export function ErrorState({ error, retry }: { error: any, retry?: () => void }) {
  return (
    <div className="min-h-[50vh] flex flex-col items-center justify-center text-destructive gap-4 p-6 text-center">
      <div className="h-12 w-12 rounded-full bg-destructive/10 flex items-center justify-center">
        <span className="text-xl font-bold">!</span>
      </div>
      <div>
        <h3 className="font-semibold text-lg text-foreground">Something went wrong</h3>
        <p className="text-sm text-muted-foreground max-w-md mt-1">
          {error?.message || error?.error || String(error)}
        </p>
      </div>
      {retry && (
        <button 
          onClick={retry}
          className="px-4 py-2 mt-2 rounded-md bg-secondary text-secondary-foreground text-sm font-medium hover:bg-secondary/80 transition-colors"
        >
          Try Again
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, description, action }: { title: string, description: string, action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center border border-dashed rounded-xl bg-muted/30">
      <h3 className="mt-4 text-lg font-semibold">{title}</h3>
      <p className="mb-4 mt-2 text-sm text-muted-foreground max-w-sm">{description}</p>
      {action}
    </div>
  )
}
