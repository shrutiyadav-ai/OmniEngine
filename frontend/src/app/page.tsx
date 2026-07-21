'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/chat');
  }, [router]);

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-background text-gray-400">
      <p>Redirecting to OmniEngine Chat...</p>
    </div>
  );
}
