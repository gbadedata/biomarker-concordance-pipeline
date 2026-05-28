#!/usr/bin/env nextflow
nextflow.enable.dsl = 2

/*
 * Biomarker Concordance Pipeline
 *
 * Usage:
 *   nextflow run main.nf -profile test
 *   nextflow run main.nf -profile local --input samplesheet.csv --fasta /ref/GRCh38.fa
 *   nextflow run main.nf -profile aws   --input s3://bucket/samplesheet.csv
 */

include { GERMLINE_VARIANT_CALLING } from './workflows/germline_variant_calling'


def validate_samplesheet(path) {
    return Channel
        .fromPath(path, checkIfExists: true)
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
                ? [ file(row.fastq_1, checkIfExists: true) ]
                : [ file(row.fastq_1, checkIfExists: true), file(row.fastq_2, checkIfExists: true) ]
            [ meta, reads ]
        }
}


workflow {

    ch_input     = validate_samplesheet(params.input)
    ch_fasta     = file(params.fasta,     checkIfExists: true)
    ch_fasta_fai = file(params.fasta_fai, checkIfExists: true)
    ch_fasta_dict = file(params.fasta.replaceAll(/\.(fa|fasta)(\.gz)?$/, '.dict'))

    GERMLINE_VARIANT_CALLING(
        ch_input,
        ch_fasta,
        ch_fasta_fai,
        ch_fasta_dict,
        params.bwa_index        ? file(params.bwa_index)        : null,
        file(params.dbsnp,       checkIfExists: true),
        file(params.dbsnp_tbi,   checkIfExists: true),
        file(params.known_indels,     checkIfExists: true),
        file(params.known_indels_tbi, checkIfExists: true),
        file(params.giab_truth_vcf,   checkIfExists: true),
        file(params.giab_truth_tbi,   checkIfExists: true),
        file(params.giab_truth_bed,   checkIfExists: true),
        params.vep_cache ? file(params.vep_cache) : [],
    )

    GERMLINE_VARIANT_CALLING.out.versions
        .unique()
        .collectFile(name: 'versions.yml', storeDir: "${params.outdir}/pipeline_info")
}


workflow.onComplete {
    log.info """
    ================================================
    Biomarker Concordance Pipeline complete
    ================================================
    Status   : ${workflow.success ? 'SUCCESS' : 'FAILED'}
    Duration : ${workflow.duration}
    Output   : ${params.outdir}
    Work dir : ${workflow.workDir}
    ================================================
    """.stripIndent()
}

workflow.onError {
    log.error "Pipeline failed: ${workflow.errorMessage}"
}
