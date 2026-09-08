document.addEventListener("DOMContentLoaded", function () {

    const camposCantidad = document.querySelectorAll(
        ".cantidad-billetes"
    );

    const cantidadTotalElemento = document.getElementById(
        "cantidad-total-billetes"
    );

    const dineroTotalElemento = document.getElementById(
        "dinero-total-billetes"
    );

    const botonLimpiar = document.getElementById(
        "limpiar-contador"
    );


    const formatearDinero = function (importe) {

        return new Intl.NumberFormat(
            "es-AR",
            {
                style: "currency",
                currency: "ARS",
                maximumFractionDigits: 0
            }
        ).format(importe);

    };


    const calcularTotales = function () {

        let cantidadTotal = 0;
        let dineroTotal = 0;

        camposCantidad.forEach(function (campo) {

            const denominacion = Number(
                campo.dataset.denominacion
            );

            let cantidad = Number(campo.value);

            if (
                !Number.isFinite(cantidad)
                || cantidad < 0
            ) {
                cantidad = 0;
            }

            cantidad = Math.floor(cantidad);

            const subtotal = denominacion * cantidad;

            cantidadTotal += cantidad;
            dineroTotal += subtotal;

            const fila = campo.closest("tr");

            const subtotalElemento = fila.querySelector(
                ".subtotal-billetes"
            );

            subtotalElemento.textContent = formatearDinero(
                subtotal
            );

        });

        cantidadTotalElemento.textContent = cantidadTotal;

        dineroTotalElemento.textContent = formatearDinero(
            dineroTotal
        );

    };


    camposCantidad.forEach(function (campo) {

        campo.addEventListener(
            "input",
            calcularTotales
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

            const confirmar = window.confirm(
                "¿Querés borrar todas las cantidades?"
            );

            if (!confirmar) {
                return;
            }

            camposCantidad.forEach(function (campo) {
                campo.value = 0;
            });

            calcularTotales();

            if (camposCantidad.length > 0) {
                camposCantidad[0].focus();
            }

        }
    );


    calcularTotales();

});