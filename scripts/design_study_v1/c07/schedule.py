"""Prospective C07 firmware request/bank schedule, including empty requests."""
CONDITIONS=('reference_B001','C07_zero_off','C07_zero_on')


def requests(ordinal):
    if ordinal not in range(4):raise ValueError('ABBA ordinal')
    kind=ordinal in (1,2);base=0 if ordinal<2 else 3
    token_bank=int(ordinal==3);frame_id=0
    # Every successful request, even empty, updates the same publication token.
    for case in range(68):
        for order in range(2 if kind else 1):
            token_bank^=1;frame_id+=1
    for local in range(3):
        repeat=base+local
        for case in range(68):
            for order in range(2 if kind else 1):
                condition=1+((repeat+case+order)&1) if kind else 0
                token_bank^=1;frame_id+=1
                yield {'case_index':case,'frame_index':case//17,'mask_index':case%17,
                    'condition':CONDITIONS[condition],'condition_id':condition,
                    'global_repeat':repeat,'private_bank':token_bank,'frame_id':frame_id,
                    'published_frame_bank_token':(frame_id<<1)|token_bank,
                    'archive_required':repeat==0}
