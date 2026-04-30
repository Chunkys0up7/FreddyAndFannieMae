import type { Metadata } from "next";
import "./globals.css";
import "@copilotkit/react-ui/styles.css";
import { CopilotKit } from "@copilotkit/react-core";

export const metadata: Metadata = {
  title: "GSE Guideline Copilot",
  description: "Fannie Mae and Freddie Mac selling/servicing guide intelligence",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <CopilotKit runtimeUrl="/api/copilotkit" agent="gse_copilot">
          {children}
        </CopilotKit>
      </body>
    </html>
  );
}
