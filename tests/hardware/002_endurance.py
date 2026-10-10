"""Three-minute per-mode on-device run, with injected gameplay and sound controls."""
passed=0
failed=0
try:
    import crankfruit
    crankfruit.main(test=True,endurance=180000)
    passed+=1
    print('PASS: three minutes each source game and sound explorer, plus library/start/return')
except Exception as error:
    failed+=1
    print('FAIL: player endurance:',repr(error))
finally:
    print('summary:',passed,'passed;',failed,'failed')
    print('~~END~~')
