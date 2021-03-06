#!/usr/bin/env python
# Copyright 2017 Calico LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========================================================================

from optparse import OptionParser
import gc
import glob
import os
import pickle
import shutil
import subprocess

import numpy as np

import slurm

'''
basenji_sad_multi.py

Compute SNP expression difference scores for variants in a VCF file,
using multiple processes.
'''

################################################################################
# main
################################################################################
def main():
    usage = 'usage: %prog [options] <params_file> <model_file> <vcf_file>'
    parser = OptionParser(usage)
    parser.add_option('-b', dest='batch_size', default=256, type='int', help='Batch size [Default: %default]')
    parser.add_option('-c', dest='csv', default=False, action='store_true', help='Print table as CSV [Default: %default]')
    parser.add_option('-e', dest='heatmaps', default=False, action='store_true', help='Draw score heatmaps, grouped by index SNP [Default: %default]')
    parser.add_option('-f', dest='genome_fasta', default='%s/assembly/hg19.fa'%os.environ['HG19'], help='Genome FASTA from which sequences will be drawn [Default: %default]')
    parser.add_option('-g', dest='genome_file', default='%s/assembly/human.hg19.genome'%os.environ['HG19'], help='Chromosome lengths file [Default: %default]')
    parser.add_option('-i', dest='index_snp', default=False, action='store_true', help='SNPs are labeled with their index SNP as column 6 [Default: %default]')
    parser.add_option('-l', dest='seq_len', type='int', default=1024, help='Sequence length provided to the model [Default: %default]')
    parser.add_option('-m', dest='min_limit', default=0.1, type='float', help='Minimum heatmap limit [Default: %default]')
    parser.add_option('-o', dest='out_dir', default='sad', help='Output directory for tables and plots [Default: %default]')
    parser.add_option('-p', dest='processes', default=2, type='int', help='Number of parallel processes to run.')
    parser.add_option('-q', dest='queue', default='p100', help='SLURM queue on which to run the jobs [Default: %default]')
    parser.add_option('--rc', dest='rc', default=False, action='store_true', help='Average the forward and reverse complement predictions when testing [Default: %default]')
    parser.add_option('-s', dest='score', default=False, action='store_true', help='SNPs are labeled with scores as column 7 [Default: %default]')
    parser.add_option('-t', dest='targets_file', default=None, help='File specifying target indexes and labels in table format')
    parser.add_option('--ti', dest='track_indexes', help='Comma-separated list of target indexes to output BigWig tracks')
    (options,args) = parser.parse_args()

    if len(args) != 3:
        parser.error('Must provide parameters and model files and VCF file')
    else:
        params_file = args[0]
        model_file = args[1]
        vcf_file = args[2]

    #######################################################
    # prep work

    # output directory
    if os.path.isdir(options.out_dir):
        shutil.rmtree(options.out_dir)
    os.mkdir(options.out_dir)

    # pickle options
    options_pkl_file = '%s/options.pkl' % options.out_dir
    options_pkl = open(options_pkl_file, 'wb')
    pickle.dump(options, options_pkl)
    options_pkl.close()

    #######################################################
    # launch worker threads
    jobs = []
    for pi in range(options.processes):
        cmd = 'source activate py3_gpu; basenji_sad.py %s %s %d' % (options_pkl_file, ' '.join(args), pi)
        name = 'sad_p%d'%pi
        outf = '%s/job%d.out' % (options.out_dir,pi)
        errf = '%s/job%d.err' % (options.out_dir,pi)
        j = slurm.Job(cmd, name, outf, errf, queue=options.queue, mem=16000, time='4:0:0', gpu=1)
        jobs.append(j)

    slurm.multi_run(jobs, max_proc=options.processes, verbose=True, sleep_time=60)

    #######################################################
    # collect output

    collect_table('sad_table.txt', options.out_dir, options.processes)

    # for pi in range(options.processes):
    #     shutil.rmtree('%s/job%d' % (options.out_dir,pi))


def collect_table(file_name, out_dir, num_procs):
    os.rename('%s/job0/%s' % (out_dir, file_name), '%s/%s' % (out_dir, file_name))
    for pi in range(1, num_procs):
        subprocess.call('tail -n +2 %s/job%d/%s >> %s/%s' % (out_dir, pi, file_name, out_dir, file_name), shell=True)


################################################################################
# __main__
################################################################################
if __name__ == '__main__':
    main()
