# Latin American Spanish. Same plain tone as the English: no hype, especially
# on the pad warning. Brand name, LINE/EXT, epson.com and model names stay as-is.

STRINGS = {
    "app_title": "Pad Zero",
    "what_is_this": "¿Qué es esto?",
    "looking_for_printer": "Buscando tu impresora...",
    "technical_details_closed": "▸  Detalles técnicos",
    "technical_details_open": "▾  Detalles técnicos",
    "reset_the_counter": "Resetear el contador",
    "check_level_now": "Comprobar nivel",
    "save_a_backup": "Guardar una copia",
    "lost_connection_status": "Se perdió la conexión con la impresora",
    "lost_connection_body": (
        "Pad Zero no pudo conectar bien con la impresora.\n\n"
        "Casi siempre es una conexión USB atascada, no un fallo físico.\n\n"
        "Prueba esto:\n"
        "1. Desconecta el cable USB, espera unos segundos y vuelve a conectarlo.\n"
        "2. Pulsa Resetear otra vez.\n\n"
        "Si sigue fallando, reinicia el PC e inténtalo de nuevo: eso limpia la "
        "conexión USB por completo."
    ),
    "something_went_wrong": "Algo salió mal: {error}",
    "no_counter_data": "sin datos de contador",
    "no_readable_counters": "sin contadores legibles",
    "counter_read_ok": "lectura del contador OK",
    "nothing_to_clear_short": "nada que borrar",
    "stored_value_one": "{n} valor guardado",
    "stored_value_other": "{n} valores guardados",
    "readings_this_session": "LECTURAS DE ESTA SESIÓN",
    "printer_connected_checking": "Impresora conectada, comprobando...",
    "printer_unplugged": "Impresora desconectada",
    "checking_usb": "Comprobando la conexión USB...",
    "no_printer_found": "No se encontró ninguna impresora",
    "no_printer_verdict": (
        "No hay respuesta en el USB. Casi siempre es una de las siguientes cosas, "
        "y son fáciles de revisar."
    ),
    "step_socket_title": "Revisa en qué puerto está el cable",
    "step_socket_body": (
        "El cable USB tiene que ir en el puerto USB plano y ancho. Los dos "
        "conectores cuadrados pequeños marcados LINE y EXT son tomas telefónicas "
        "del fax y no sirven para esto."
    ),
    "step_driver_title": "Instala el driver de Epson",
    "step_driver_body": (
        "Windows instala un driver básico que puede imprimir pero no habla "
        "bien con la impresora. Descarga el de tu modelo en epson.com, instálalo "
        "y pulsa Comprobar otra vez."
    ),
    "step_power_title": "Asegúrate de que la impresora esté encendida",
    "step_power_body": (
        "Debe estar encendida y haber terminado de arrancar, no a mitad "
        "del inicio."
    ),
    "not_connected": "Sin conexión",
    "untested_verdict": (
        "Esta impresora funciona, pero Pad Zero nunca se ha probado en este "
        "modelo, por lo que no modificará nada en ella."
    ),
    "help_add_model_title": "Ayuda a añadir tu modelo",
    "help_add_model_body": (
        "Pulsa Guardar una copia y envía el archivo que aparece. Trae los "
        "ajustes necesarios para soportar tu impresora."
    ),
    "open_issue_tracker": "Abrir el seguimiento de incidencias",
    "model_not_recognised": "Modelo no reconocido. Solo lectura.",
    "connected_no_percent": (
        "Conectada y funcionando. Este modelo no reporta un porcentaje, pero "
        "el contador igual se puede resetear."
    ),
    "ready": "Lista",
    "counter_full_verdict": (
        "El contador de tinta residual está lleno. Por eso la impresora dejó "
        "de imprimir."
    ),
    "counter_full_status": "Contador lleno",
    "nearly_full_verdict": "Casi lleno. La impresora dejará de imprimir pronto.",
    "nearly_full_status": "Casi lleno",
    "everything_fine": "Todo bien. No tienes que hacer nada.",
    "healthy": "En buen estado",
    "about_percentages": "Sobre estos porcentajes",
    "about_percentages_body": (
        "Este modelo exacto aún no está en la base de porcentajes, así que las "
        "cifras de arriba se calculan a partir de {n} modelos Epson parecidos "
        "que guardan los contadores en los mismos sitios. Tómalas como una buena "
        "estimación, no como una lectura exacta. El reseteo en sí no cambia."
    ),
    "how_full": "CUÁN LLENO ESTÁ EL CONTADOR",
    "before_and_after": "ANTES Y DESPUÉS",
    "approximate_suffix": "   (APROXIMADO)",
    "waste_counter_heading": "CONTADOR DE RESIDUAL",
    "nothing_to_clear": "Nada que borrar",
    "nothing_to_clear_body": (
        "El contador de residual de esta impresora ya está en su valor más bajo. "
        "Pad Zero no tiene nada que resetear, y tú no tienes que hacer nada."
    ),
    "some_usage": "Hay uso registrado",
    "some_usage_body_one": (
        "Resetear borraría {n} valor guardado. Esta impresora no reporta un "
        "porcentaje, así que Pad Zero no puede mostrarte una barra, pero el "
        "reseteo funciona igual."
    ),
    "some_usage_body_other": (
        "Resetear borraría {n} valores guardados. Esta impresora no reporta un "
        "porcentaje, así que Pad Zero no puede mostrarte una barra, pero el "
        "reseteo funciona igual."
    ),
    "counter_read_successfully": "Contador leído bien",
    "counter_read_successfully_body": (
        "Esta impresora no reporta su nivel como porcentaje. Pad Zero aún "
        "puede leerlo y resetearlo."
    ),
    "exact_numbers_hint": "Los números exactos están en Detalles técnicos, abajo.",
    "resetting_will_not_empty": "Resetear no vacía las almohadillas",
    "pad_advice_body": (
        "El contador solo es una estimación de cuánta tinta ha empapado las "
        "almohadillas dentro de la impresora. Resetearlo te deja imprimir otra "
        "vez, pero la tinta sigue ahí. Si las almohadillas están llenas, con el "
        "tiempo puede salirse por abajo.\n\n"
        "Pon una toalla o una bandeja debajo de la impresora, y pide una "
        "almohadilla de reemplazo o un kit de tinta residual."
    ),
    "where_to_buy_pad": "Dónde comprar una almohadilla",
    "nothing_connected": "Nada conectado.",
    "reading_memory": "Leyendo memoria de la impresora; tardará un momento...",
    "backup_saved_status": "Copia guardada",
    "backup_saved_title": "Copia guardada",
    "backup_saved_body": (
        "Se guardó una copia de los ajustes de tu impresora en:\n\n{path}\n\n"
        "Consérvala. Si algo sale mal, sirve para dejar las cosas como estaban."
    ),
    "no_reset_known": (
        "No hay un reseteo conocido para este modelo, así que no se va a "
        "cambiar nada."
    ),
    "reset_confirm_title": "¿Resetear el contador de tinta residual?",
    "reset_confirm_body": (
        "Esto le dice a tu {model} que las almohadillas de tinta residual están "
        "vacías, para que vuelva a imprimir.\n\n"
        "ESTO NO VACÍA LAS ALMOHADILLAS.\n\n"
        "La tinta sigue dentro de la impresora. Si las almohadillas están llenas, "
        "la tinta puede salirse por abajo sobre lo que tenga debajo. Pon una "
        "toalla y cambia la almohadilla cuando puedas.\n\n"
        "Antes de cambiar nada se guarda una copia sola.\n\n"
        "¿Seguimos?"
    ),
    "cancelled": "Cancelado",
    "saving_backup_then_resetting": "Guardando una copia y luego reseteando...",
    "after_reset_note": "<- tras reseteo",
    "done_power_cycle": "Listo. Apaga la impresora y vuélvela a encender.",
    "reset_complete_title": "Reseteo listo",
    "reset_complete_body": (
        "El contador se reseteó.\n\n"
        "SIGUIENTE: apaga la impresora, espera diez segundos y enciéndela otra vez. "
        "Debería imprimir nuevamente.\n\n"
        "Luego ordena una almohadilla de repuesto. La tinta sigue dentro de la "
        "impresora y esto volverá a pasar.\n\n"
        "Copia guardada en:\n{path}"
    ),
    "some_changes_refused": "Algunos cambios se rechazaron",
    "reset_did_not_finish_title": "El reseteo no terminó",
    "reset_did_not_finish_body": (
        "La impresora rechazó algunos de los cambios.\n\n"
        "Tu copia está a salvo en:\n{path}\n\n"
        "Casi siempre significa que el firmware de la impresora bloquea los "
        "reseteos. No se dañó nada."
    ),
    "what_pad_zero_does": "Qué hace Pad Zero",
    "explain_body": (
        "Qué hace esta herramienta, y qué no hace\n\n"
        "  Tu impresora lleva un contador que estima cuánta tinta residual ha\n"
        "  ido a las almohadillas internas. No hay un sensor. Es una estimación\n"
        "  que sube cada vez que la impresora limpia su cabezal, carga tinta,\n"
        "  se enciende o imprime sin bordes.\n\n"
        "  Cuando esa estimación cruza un umbral, la impresora se niega a imprimir\n"
        "  y te dice que contactes a Epson.\n\n"
        "  Esta herramienta pone el contador en cero. Eso es todo lo que hace.\n\n"
        "  NO vacía las almohadillas. La tinta sigue ahí. Si las almohadillas\n"
        "  estaban realmente saturadas, resetear el contador significa que la\n"
        "  impresora sigue metiendo tinta en una esponja llena, y eventualmente esa\n"
        "  tinta saldrá por debajo hacia la superficie en la que repose.\n\n"
        "  La solución real es cambiar la almohadilla o poner un tanque\n"
        "  residual externo. Resetea el contador para volver a imprimir, y\n"
        "  después haz el arreglo correcto.\n\n"
        "  Mientras tanto, pon algo absorbente bajo la impresora."
    ),
    "close": "Cerrar",
    "could_not_open_window": (
        "Pad Zero no pudo abrir su ventana.\n\n{error}\n\n"
        "Suele ser una instalación de Tcl/Tk faltante."
    ),
    "could_not_start": "No se pudo iniciar: {error}",
    "stopped_unexpectedly_title": "Pad Zero se detuvo inesperadamente",
    "stopped_unexpectedly_body": (
        "Algo salió mal.\n\nCopia esto y abre una incidencia en:\n{url}\n\n{detail}"
    ),
}
