import { redirect } from "next/navigation";

// Signed-out visitors are sent to /login by middleware before reaching here.
export default function Home() {
  redirect("/dashboard");
}
