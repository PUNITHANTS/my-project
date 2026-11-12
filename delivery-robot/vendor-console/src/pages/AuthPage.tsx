import { useState } from "react";
import { register } from "../api/auth";

interface AuthPageProps {
  onLogin: (username: string, password: string) => Promise<boolean>;
}

const EMPTY_SIGNUP = {
  username: "",
  password: "",
  confirmPassword: "",
  vendorName: "",
  phone: "",
  address: "",
};

export default function AuthPage({ onLogin }: AuthPageProps) {
  const [mode, setMode] = useState<"login" | "signup">("login");

  // Login state
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // Signup state
  const [signup, setSignup] = useState(EMPTY_SIGNUP);

  const [message, setMessage] = useState<{ text: string; type: "error" | "success" } | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  function setField(field: keyof typeof EMPTY_SIGNUP, value: string) {
    setSignup((p) => ({ ...p, [field]: value }));
  }

  async function handleLogin() {
    setIsLoading(true);
    setMessage(null);
    try {
      const ok = await onLogin(username, password);
      if (!ok) setMessage({ text: "Invalid credentials. Check your username and password.", type: "error" });
    } catch {
      setMessage({ text: "Could not reach the server. Make sure the backend is running.", type: "error" });
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSignup() {
    if (!signup.username || !signup.password || !signup.vendorName) {
      setMessage({ text: "Username, password, and vendor name are required.", type: "error" });
      return;
    }
    if (signup.password !== signup.confirmPassword) {
      setMessage({ text: "Passwords do not match.", type: "error" });
      return;
    }
    if (signup.password.length < 8) {
      setMessage({ text: "Password must be at least 8 characters.", type: "error" });
      return;
    }

    setIsLoading(true);
    setMessage(null);
    try {
      const result = await register({
        username: signup.username,
        password: signup.password,
        confirm_password: signup.confirmPassword,
        vendor_name: signup.vendorName,
        phone: signup.phone,
        address: signup.address,
      });
      if (result === true) {
        setMessage({ text: "Account created! You can now log in.", type: "success" });
        setSignup(EMPTY_SIGNUP);
        setUsername(signup.username);
        setTimeout(() => setMode("login"), 1500);
      } else {
        setMessage({ text: result, type: "error" });
      }
    } catch {
      setMessage({ text: "Could not reach the server. Try again later.", type: "error" });
    } finally {
      setIsLoading(false);
    }
  }

  const inputClass =
    "w-full mt-1 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded text-sm focus:outline-none focus:border-orange-500 transition-colors";
  const labelClass = "block text-xs text-zinc-400 mt-3";

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-xl">
        <h1 className="font-mono text-2xl font-bold text-center">Campus Eats</h1>
        <p className="text-zinc-400 text-sm text-center mt-1">Vendor Console Access</p>

        <div className="mt-6 grid grid-cols-2 bg-zinc-800 rounded p-1">
          <button
            onClick={() => { setMode("login"); setMessage(null); }}
            className={`rounded py-2 text-sm font-semibold ${mode === "login" ? "bg-zinc-700 text-zinc-100" : "text-zinc-400"}`}
          >
            Login
          </button>
          <button
            onClick={() => { setMode("signup"); setMessage(null); }}
            className={`rounded py-2 text-sm font-semibold ${mode === "signup" ? "bg-zinc-700 text-zinc-100" : "text-zinc-400"}`}
          >
            Sign Up
          </button>
        </div>

        {mode === "login" ? (
          <div className="mt-5 space-y-1">
            <label className={labelClass}>
              Username
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                className={inputClass}
                placeholder="vendor"
                autoComplete="username"
              />
            </label>
            <label className={labelClass}>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                className={inputClass}
                placeholder="vendorpassword123"
                autoComplete="current-password"
              />
            </label>
            <button
              onClick={handleLogin}
              disabled={isLoading}
              className="w-full mt-4 py-2 bg-orange-500 hover:bg-orange-400 disabled:opacity-50 disabled:cursor-not-allowed text-black rounded font-semibold text-sm"
            >
              {isLoading ? "Logging in…" : "Log In"}
            </button>
          </div>
        ) : (
          <div className="mt-5 space-y-1">
            <label className={labelClass}>
              Vendor Name *
              <input
                value={signup.vendorName}
                onChange={(e) => setField("vendorName", e.target.value)}
                className={inputClass}
                placeholder="Campus Eats"
              />
            </label>
            <label className={labelClass}>
              Username *
              <input
                value={signup.username}
                onChange={(e) => setField("username", e.target.value)}
                className={inputClass}
                placeholder="your_username"
                autoComplete="username"
              />
            </label>
            <label className={labelClass}>
              Password *
              <input
                type="password"
                value={signup.password}
                onChange={(e) => setField("password", e.target.value)}
                className={inputClass}
                placeholder="Min. 8 characters"
                autoComplete="new-password"
              />
            </label>
            <label className={labelClass}>
              Confirm Password *
              <input
                type="password"
                value={signup.confirmPassword}
                onChange={(e) => setField("confirmPassword", e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSignup()}
                className={inputClass}
                placeholder="Repeat password"
                autoComplete="new-password"
              />
            </label>
            <label className={labelClass}>
              Contact Number
              <input
                type="tel"
                value={signup.phone}
                onChange={(e) => setField("phone", e.target.value)}
                className={inputClass}
                placeholder="Optional"
              />
            </label>
            <label className={labelClass}>
              Address / Location
              <input
                value={signup.address}
                onChange={(e) => setField("address", e.target.value)}
                className={inputClass}
                placeholder="e.g. Student Center, Building B"
              />
            </label>
            <button
              onClick={handleSignup}
              disabled={isLoading}
              className="w-full mt-4 py-2 bg-orange-500 hover:bg-orange-400 disabled:opacity-50 disabled:cursor-not-allowed text-black rounded font-semibold text-sm"
            >
              {isLoading ? "Creating account…" : "Create Account"}
            </button>
          </div>
        )}

        {message && (
          <p className={`mt-3 text-xs ${message.type === "success" ? "text-green-400" : "text-amber-300"}`}>
            {message.text}
          </p>
        )}
      </div>
    </div>
  );
}
