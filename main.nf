#!/usr/bin/env nextflow
nextflow.enable.dsl = 2

/*
 * Biomarker Concordance Pipeline
 *
 * Usage:
 *   nextflow run main.nf -profile test           # chr20 test data, stub-safe
 *   nextflow run main.nf -profile local --input samplesheet.csv --fasta /ref/GRCh38.fa
 *   nextflow run main.nf -profile aws   --input s3://bucket/samplesheet.csv
 */

include { GERMLINE_VARIANT_CALLING } from './workflows/germline_variant_calling'


workflow {

    def ch_input = Channel
        .fromPath(params.input, checkIfExists: true)
        .splitCsv(header: true, strip: true)
        .map { row ->
            def meta = [
                id        : "${row.sample}_rep${row.replicate}",
                sample    : row.sample,
                replicate : row.replicate.toInteger(),
                sex       : row.sex,
                single_end: row.single_end == 'TRUE',
            ]
            def reads = row.single_end == 'TRUE'
                ? [ file(row.fastq_1) ]
                : [ file(row.fastq_1), file(row.fastq_2) ]
            [ meta, reads ]
        }

    def ch_fasta      = file(params.fasta)
    def ch_fasta_fai  = file(params.fasta_fai)
    def ch_fasta_dict = file(params.fasta.replaceAll(/\.(fa|fasta)(\.gz)?$/, '.dict'))

    GERMLINE_VARIANT_CALLING(
        ch_input,
        ch_fasta,
        ch_fasta_fai,
        ch_fasta_dict,
        params.bwa_index        ? file(params.bwa_index)        : null,
        file(params.dbsnp),
        file(params.dbsnp_tbi),
        file(params.known_indels),
        file(params.known_indels_tbi),
        file(params.giab_truth_vcf),
        file(params.giab_truth_tbi),
        file(params.giab_truth_bed),
        params.vep_cache ? file(params.vep_cache) : [],
    )

    GERMLINE_VARIANT_CALLING.out.versions
        .unique()
        .collectFile(name: 'versions.yml', storeDir: "${params.outdir}/pipeline_info")
}
