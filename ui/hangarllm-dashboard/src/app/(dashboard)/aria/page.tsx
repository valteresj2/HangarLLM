"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { DOCKWORKER_ROUTE } from "@/components/liteadmin/aria-brand";
import { LiteAdminPage } from "@/components/liteadmin/LiteAdmin";
import { uiHref } from "@/utils/uiHref";

export default function LegacyAriaPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace(`${uiHref(DOCKWORKER_ROUTE)}${window.location.search}${window.location.hash}`);
  }, [router]);
  return <LiteAdminPage />;
}
