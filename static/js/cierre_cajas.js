document.addEventListener("DOMContentLoaded", function () {

    const filasCajas = document.querySelectorAll(
        ".fila-caja"
    );

    const camposImporte = document.querySelectorAll(
        ".importe-cierre"
    );

    const totalPosnetInmersivoElemento =
        document.getElementById(
            "total-posnet-inmersivo"
        );

    const totalPosnetNormalElemento =
        document.getElementById(
            "total-posnet-normal"
        );

    const totalTarjetasElemento =
        document.getElementById(
            "total-tarjetas"
        );

    const efectivoTotalElemento =
        document.getElementById(
            "efectivo-total"
        );

    const recaudacionTotalElemento =
        document.getElementById(
            "recaudacion-total"
        );

    const advertenciaElemento =
        document.getElementById(
            "advertencia-cierre"
        );

    const botonLimpiar =
        document.getElementById(
            "limpiar-cierre"
        );


    function obtenerImporte(campo) {

        const importe = Number(campo.value);

        if (
            !Number.isFinite(importe)
            || importe < 0
        ) {
            return 0;
        }

        return importe;

    }


    function redondearImporte(importe) {

        return Math.round(
            (importe + Number.EPSILON) * 100
        ) / 100;

    }


    function formatearDinero(importe) {

        return new Intl.NumberFormat(
            "es-AR",
            {
                style: "currency",
                currency: "ARS",
                minimumFractionDigits: 0,
                maximumFractionDigits: 2
            }
        ).format(importe);

    }


    function calcularCierre() {

        let totalPosnetInmersivo = 0;
        let totalPosnetNormal = 0;
        let totalCierreZ = 0;
        let efectivoTotal = 0;
        let existeDiferenciaNegativa = false;


        filasCajas.forEach(function (fila) {

            const posnetInmersivo = obtenerImporte(
                fila.querySelector(
                    ".posnet-inmersivo"
                )
            );

            const posnetNormal = obtenerImporte(
                fila.querySelector(
                    ".posnet-normal"
                )
            );

            const cierreZ = obtenerImporte(
                fila.querySelector(
                    ".cierre-z"
                )
            );

            const efectivoCaja = redondearImporte(
                cierreZ
                - posnetInmersivo
                - posnetNormal
            );

            const efectivoCajaElemento =
                fila.querySelector(
                    ".efectivo-caja"
                );

            efectivoCajaElemento.textContent =
                formatearDinero(efectivoCaja);

            efectivoCajaElemento.classList.toggle(
                "resultado-negativo",
                efectivoCaja < 0
            );

            if (efectivoCaja < 0) {
                existeDiferenciaNegativa = true;
            }

            totalPosnetInmersivo += posnetInmersivo;
            totalPosnetNormal += posnetNormal;
            totalCierreZ += cierreZ;
            efectivoTotal += efectivoCaja;

        });


        totalPosnetInmersivo = redondearImporte(
            totalPosnetInmersivo
        );

        totalPosnetNormal = redondearImporte(
            totalPosnetNormal
        );

        totalCierreZ = redondearImporte(
            totalCierreZ
        );

        efectivoTotal = redondearImporte(
            efectivoTotal
        );

        const totalTarjetas = redondearImporte(
            totalPosnetInmersivo
            + totalPosnetNormal
        );


        totalPosnetInmersivoElemento.textContent =
            formatearDinero(
                totalPosnetInmersivo
            );

        totalPosnetNormalElemento.textContent =
            formatearDinero(
                totalPosnetNormal
            );

        totalTarjetasElemento.textContent =
            formatearDinero(
                totalTarjetas
            );

        efectivoTotalElemento.textContent =
            formatearDinero(
                efectivoTotal
            );

        recaudacionTotalElemento.textContent =
            formatearDinero(
                totalCierreZ
            );

        advertenciaElemento.hidden =
            !existeDiferenciaNegativa;

    }


    camposImporte.forEach(function (campo) {

        campo.addEventListener(
            "input",
            calcularCierre
        );

        campo.addEventListener(
            "focus",
            function () {
                campo.select();
            }
        );

    });


    botonLimpiar.addEventListener(
        "click",
        function () {

            const confirmado = window.confirm(
                "¿Querés borrar todos los importes del cierre?"
            );

            if (!confirmado) {
                return;
            }

            camposImporte.forEach(function (campo) {
                campo.value = 0;
            });

            calcularCierre();

            if (camposImporte.length > 0) {
                camposImporte[0].focus();
            }

        }
    );


    calcularCierre();

});