import Image from "next/image";

import { branding } from "@/helpers/branding";

const Footer = () => {
  const CURRENT_YEAR = new Date().getFullYear();

  return (
    <footer className="bg-gray-700 text-gray-300">
      <div className="mx-auto max-w-7xl px-4 py-12">
        {/* Top Section */}
        <div className="mb-8 grid grid-cols-1 gap-8 md:grid-cols-2">
          {/* Brand */}
          <div>
            <div className="mb-4 flex items-center gap-2">
              {/* Logo/Icon */}
              <div className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-lg">
                <Image
                  src="/travel-photo-logo.png"
                  alt={branding.appName}
                  width={32}
                  height={32}
                  className="h-full w-full object-contain"
                />
              </div>
              <span className="font-bold text-white">{branding.appName}</span>
            </div>
            <p className="text-sm text-gray-400">{branding.description}</p>
          </div>

          {/* Contact */}
          <div className="text-right">
            <h4 className="mb-4 font-semibold text-white">Contacto</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <a href={`mailto:${branding.supportEmail}`} className="hover:text-blue-400">
                  Email: {branding.supportEmail}
                </a>
              </li>
              <li>
                <a href={branding.github} className="hover:text-blue-400">
                  Github: github.com/bcesano20
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Divider */}
        <hr className="border-gray-800" />

        {/* Bottom */}
        <div className="flex items-center justify-between pt-8 text-sm text-gray-400">
          <p>
            &copy; {CURRENT_YEAR} {branding.appName}. Todos los derechos reservados.
            <br />
            Version 1.0.0
          </p>
          <p> Desarrollado por Bruno Cesano</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
