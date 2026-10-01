/**
 * Marca del Motor de Validación: la hoja de un expediente con su check de
 * validación y la esquina doblada en sólido, como el sello del documento
 * custodiado. Trazo de 1.75 en `currentColor`, coherente con los iconos de
 * Lucide, así que toma el color de su contenedor en ambos temas. Es la marca
 * del sistema, no el logotipo de PluriOne. El favicon (public/favicon.svg)
 * dibuja la misma figura.
 */
export default function LogoMotor({ size = 16 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M13.5 3.5H8A2.5 2.5 0 0 0 5.5 6v12A2.5 2.5 0 0 0 8 20.5h8a2.5 2.5 0 0 0 2.5-2.5V8.5z" />
      <path d="M13.5 3.5v3a2 2 0 0 0 2 2h3z" fill="currentColor" />
      <path d="M8.75 14.25l2.25 2.25 4.5-5" />
    </svg>
  )
}
