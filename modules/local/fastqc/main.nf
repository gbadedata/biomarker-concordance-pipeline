process FASTQC {
    tag "${meta.id}"
    label 'process_low'
    container 'biocontainers/fastqc:0.12.1--hdfd78af_0'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path('*.html'), emit: html
    tuple val(meta), path('*.zip'),  emit: zip
    path 'versions.yml',             emit: versions

    script:
    def read_list = reads instanceof List ? reads.join(' ') : reads
    """
    fastqc --threads ${task.cpus} --outdir . ${read_list}

    cat <<-VERSIONS > versions.yml
    "${task.process}":
        fastqc: \$(fastqc --version | sed 's/FastQC v//')
    VERSIONS
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}_R1_fastqc.html ${prefix}_R1_fastqc.zip
    cat <<-VERSIONS > versions.yml
    "${task.process}":
        fastqc: 0.12.1
    VERSIONS
    """
}
