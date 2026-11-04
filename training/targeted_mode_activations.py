    from targeted_mode_activations import parse as parse_targeted_mode_activation
    modal_activation=parse_targeted_mode_activation(text,types,name)
    if modal_activation:
        program=(compile_abilities(modal_activation.remaining_text,name)
                 if modal_activation.remaining_text else None)
        if modal_activation.remaining_text and program is None:
            return Definition(**base,abilities=frozenset(),supported=False,
                              reason='Unparsed rules remaining beside modal activation')
        parts=dict(vars(program)) if program else {}
        keywords=parts.pop('keywords',frozenset())
        return Definition(**base,abilities=keywords,modal_activation=modal_activation,**parts)
