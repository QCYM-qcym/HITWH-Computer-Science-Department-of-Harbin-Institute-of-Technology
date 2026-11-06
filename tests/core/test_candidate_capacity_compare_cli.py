"""Separate bounded capacity CLI; no IF, model execution or classic changes."""
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest

from .test_candidate_capacity_comparison import packages,SOURCE,SLOTS,compare
from .test_candidate_ae_capacity_artifacts import upstream


def api():return importlib.import_module('traffic_anomaly.candidate_capacity_compare_cli')


def arguments(packages):
    result=['--records',str(packages[1]),'--inputs',str(packages[2]),'--source-fixture',str(SOURCE)]
    for path in reversed(packages[0].values()):result+=['--ae-run',str(path)]
    return result


def test_cli_complete_report_equal_core_and_no_mutation(packages):
    command=[sys.executable,'-X','utf8','-m','traffic_anomaly.candidate_capacity_compare_cli',*arguments(packages)]
    completed=subprocess.run(command,capture_output=True)
    assert completed.returncode==0,completed.stderr
    assert completed.stderr==b'' and completed.stdout.endswith(b'\n')
    assert b'\r\n' not in completed.stdout and len(completed.stdout)<=1048576
    assert json.loads(completed.stdout)==compare(packages)


@pytest.mark.parametrize('kind',['missing_source','if_run','five','one','tuning','abbreviation'])
def test_invalid_cli_before_admission(packages,monkeypatch,capsys,kind):
    m=api();args=arguments(packages)
    if kind=='missing_source':i=args.index('--source-fixture');del args[i:i+2]
    elif kind=='if_run':args+=['--if-run','private-weights']
    elif kind=='five':args+=['--ae-run',str(next(iter(packages[0].values())))]
    elif kind=='one':args=args[:6]+['--ae-run',str(next(iter(packages[0].values())))]
    elif kind=='tuning':args+=['--epochs','5']
    else:args[0]='--rec'
    monkeypatch.setattr(m,'compare_candidate_ae_capacity_runs',lambda *a,**k:pytest.fail('admitted invalid request'))
    assert m.main(args)==2
    captured=capsys.readouterr()
    assert captured.out=='' and json.loads(captured.err)=={'error':'INVALID_ARGUMENTS'}


def test_cli_bounds_encoded_bytes_before_any_stdout(packages,monkeypatch,capsys):
    m=api()
    monkeypatch.setattr(m,'compare_candidate_ae_capacity_runs',lambda *a,**k:{'padding':'界'*1048576})
    assert m.main(arguments(packages))==2
    captured=capsys.readouterr()
    assert captured.out=='' and json.loads(captured.err)=={'error':'RESOURCE_LIMIT'}


@pytest.mark.parametrize('kind',['nan','unsafe_exception','runtime_exception'])
def test_no_partial_stdout_or_private_exception(packages,monkeypatch,capsys,kind):
    m=api()
    def changed(*a,**k):
        if kind=='unsafe_exception':raise OSError('private-path sentinel')
        if kind=='runtime_exception':raise RuntimeError('private-runtime sentinel')
        return {'value':float('nan')}
    monkeypatch.setattr(m,'compare_candidate_ae_capacity_runs',changed)
    assert m.main(arguments(packages))==2
    captured=capsys.readouterr()
    assert captured.out=='' and 'private' not in captured.err and 'Traceback' not in captured.err
    assert set(json.loads(captured.err))=={'error'}


def test_exact_output_boundary_and_one_byte_over(packages,monkeypatch,capsys):
    m=api();overhead=len(b'{"padding":""}\n')
    for extra in (0,1):
        monkeypatch.setattr(m,'compare_candidate_ae_capacity_runs',lambda *a,**k:{'padding':'x'*(1048576-overhead+extra)})
        status=m.main(arguments(packages));captured=capsys.readouterr()
        if extra:
            assert status==2 and captured.out=='' and json.loads(captured.err)=={'error':'RESOURCE_LIMIT'}
        else:
            assert status==0 and len(captured.out.encode('utf-8'))==1048576 and captured.err==''
