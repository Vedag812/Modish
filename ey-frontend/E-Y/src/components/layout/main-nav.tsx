
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

export function MainNav() {
  const pathname = usePathname();

  const navLinks = [
    { href: '/products', label: 'All Products' },
    { href: '/products?category=Electronics', label: 'Electronics' },
    { href: '/products?category=Appliances', label: 'Appliances' },
    { href: '/products?category=Mobile', label: 'Mobile' },
    { href: '/chatbot', label: '🤖 AI Assistant' },
  ];

  return (
    <div className="flex items-center space-x-4 lg:space-x-6">
      <nav className="hidden md:flex items-center space-x-4 lg:space-x-6">
        {navLinks.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              'text-sm font-medium transition-colors hover:text-primary',
              pathname === link.href || (link.href !== '/products' && pathname.startsWith(link.href.split('?')[0])) 
                ? 'text-primary' 
                : 'text-muted-foreground'
            )}
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
