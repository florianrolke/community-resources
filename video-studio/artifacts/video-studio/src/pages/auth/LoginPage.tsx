import { useAuth } from "@workspace/replit-auth-web"
import { Button } from "@/components/ui/button"
import { Video, ArrowRight } from "lucide-react"

export default function LoginPage() {
  const { login } = useAuth()

  return (
    <div className="min-h-[100dvh] w-full flex bg-background">
      {/* Left side - graphic/branding */}
      <div className="hidden lg:flex flex-1 bg-sidebar relative overflow-hidden items-center justify-center p-12">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 to-transparent mix-blend-overlay" />
        <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/stardust.png')] opacity-20" />
        
        <div className="relative z-10 max-w-md text-sidebar-foreground">
          <div className="w-16 h-16 rounded-2xl bg-primary flex items-center justify-center text-primary-foreground mb-8 shadow-xl shadow-primary/20">
            <Video className="w-8 h-8" />
          </div>
          <h1 className="text-4xl font-bold tracking-tight mb-4 leading-tight">
            The post-production cockpit for solo creators.
          </h1>
          <p className="text-sidebar-foreground/70 text-lg leading-relaxed">
            Record once. Let your AI clone re-voice, cut b-roll, and render in the cloud overnight.
          </p>
        </div>
      </div>
      
      {/* Right side - login */}
      <div className="flex-1 flex flex-col items-center justify-center p-8 lg:p-12 relative bg-card">
        <div className="w-full max-w-sm space-y-8">
          <div className="flex flex-col space-y-2 text-center lg:text-left">
            <div className="lg:hidden w-12 h-12 rounded-xl bg-primary flex items-center justify-center text-primary-foreground mb-4 shadow-lg mx-auto">
              <Video className="w-6 h-6" />
            </div>
            <h2 className="text-3xl font-bold tracking-tight">Welcome back</h2>
            <p className="text-muted-foreground">Sign in to access your pipeline.</p>
          </div>

          <Button 
            size="lg" 
            className="w-full h-12 text-base shadow-md group"
            onClick={() => login()}
          >
            Continue with Replit
            <ArrowRight className="w-4 h-4 ml-2 transition-transform group-hover:translate-x-1" />
          </Button>

          <p className="text-xs text-center text-muted-foreground mt-8">
            By continuing, you agree to our Terms of Service and Privacy Policy.
          </p>
        </div>
      </div>
    </div>
  )
}
