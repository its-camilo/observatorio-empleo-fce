type Props = {
  /** `oscuro` = fondo oscuro/azul (logo blanco). `claro` = fondo claro (logo negro). */
  variante?: "oscuro" | "claro";
  className?: string;
};

export default function LogoUnal({ variante = "claro", className = "" }: Props) {
  const src = variante === "oscuro" ? "/logo-unal-blanco.png" : "/logo-unal.png";
  return (
    <img
      src={src}
      alt="Universidad Nacional de Colombia"
      className={`h-8 w-auto max-w-[min(220px,55vw)] object-contain object-left md:h-11 md:max-w-[280px] ${className}`}
      width={1024}
      height={438}
      decoding="async"
    />
  );
}
